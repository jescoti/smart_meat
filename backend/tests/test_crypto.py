"""Tests for app.crypto — AES-256-GCM encrypt/decrypt functions.

Written FIRST (TDD Red phase) before any implementation exists.
"""

import base64

import pytest

from app.crypto import DecryptionError, decrypt, encrypt

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

TEST_KEY = "my-secret-encryption-key"
ANOTHER_KEY = "a-completely-different-key"


# ---------------------------------------------------------------------------
# Round-trip: encrypt then decrypt recovers original plaintext
# ---------------------------------------------------------------------------


class TestRoundTrip:
    """encrypt(plaintext, key) -> ciphertext -> decrypt(ciphertext, key) -> plaintext."""

    def test_encrypt_decrypt_simple_string(self) -> None:
        """Basic round-trip with a simple ASCII string."""
        plaintext = "hello world"
        ciphertext = encrypt(plaintext, TEST_KEY)
        assert decrypt(ciphertext, TEST_KEY) == plaintext

    def test_encrypt_decrypt_unicode(self) -> None:
        """Round-trip preserves multi-byte Unicode characters."""
        plaintext = "Hola mundo! Привет мир! 你好世界!"
        ciphertext = encrypt(plaintext, TEST_KEY)
        assert decrypt(ciphertext, TEST_KEY) == plaintext

    def test_encrypt_decrypt_long_text(self) -> None:
        """Round-trip works with large payloads."""
        plaintext = "A" * 10_000
        ciphertext = encrypt(plaintext, TEST_KEY)
        assert decrypt(ciphertext, TEST_KEY) == plaintext

    def test_encrypt_decrypt_special_characters(self) -> None:
        """Round-trip handles special characters, newlines, tabs."""
        plaintext = "line1\nline2\ttab\r\ncarriage\x00null"
        ciphertext = encrypt(plaintext, TEST_KEY)
        assert decrypt(ciphertext, TEST_KEY) == plaintext

    def test_encrypt_decrypt_json_payload(self) -> None:
        """Round-trip works with JSON-like content (common for tokens)."""
        plaintext = '{"access_token": "ya29.xxx", "refresh_token": "1//0abc"}'
        ciphertext = encrypt(plaintext, TEST_KEY)
        assert decrypt(ciphertext, TEST_KEY) == plaintext


# ---------------------------------------------------------------------------
# Ciphertext is valid base64 and differs per call (random nonce)
# ---------------------------------------------------------------------------


class TestCiphertextProperties:
    """Verify ciphertext format and non-determinism."""

    def test_ciphertext_is_valid_base64(self) -> None:
        """encrypt() output must be valid base64."""
        ciphertext = encrypt("test", TEST_KEY)
        # Should not raise
        decoded = base64.b64decode(ciphertext)
        # Must contain at least nonce (12 bytes) + some encrypted data
        assert len(decoded) > 12

    def test_different_ciphertexts_for_same_plaintext(self) -> None:
        """Two encryptions of the same plaintext must produce different ciphertexts."""
        plaintext = "same input"
        ct1 = encrypt(plaintext, TEST_KEY)
        ct2 = encrypt(plaintext, TEST_KEY)
        assert ct1 != ct2

    def test_ciphertext_is_string(self) -> None:
        """encrypt() must return a str, not bytes."""
        result = encrypt("test", TEST_KEY)
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# Decryption with wrong key must fail clearly
# ---------------------------------------------------------------------------


class TestWrongKey:
    """Decrypting with a different key must raise DecryptionError."""

    def test_decrypt_with_wrong_key_raises_error(self) -> None:
        """Using a different key for decryption must raise DecryptionError."""
        ciphertext = encrypt("secret", TEST_KEY)
        with pytest.raises(DecryptionError):
            decrypt(ciphertext, ANOTHER_KEY)

    def test_decrypt_wrong_key_error_message(self) -> None:
        """DecryptionError must include a helpful message."""
        ciphertext = encrypt("secret", TEST_KEY)
        with pytest.raises(DecryptionError, match="Decryption failed"):
            decrypt(ciphertext, ANOTHER_KEY)


# ---------------------------------------------------------------------------
# Edge cases: empty/None input
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Graceful handling of empty and invalid inputs."""

    def test_encrypt_empty_string(self) -> None:
        """Encrypting an empty string should work and round-trip."""
        ciphertext = encrypt("", TEST_KEY)
        assert decrypt(ciphertext, TEST_KEY) == ""

    def test_encrypt_none_raises_type_error(self) -> None:
        """encrypt(None, key) must raise TypeError."""
        with pytest.raises(TypeError):
            encrypt(None, TEST_KEY)  # type: ignore[arg-type]

    def test_decrypt_none_raises_type_error(self) -> None:
        """decrypt(None, key) must raise TypeError."""
        with pytest.raises(TypeError):
            decrypt(None, TEST_KEY)  # type: ignore[arg-type]

    def test_encrypt_none_key_raises_type_error(self) -> None:
        """encrypt(plaintext, None) must raise TypeError."""
        with pytest.raises(TypeError):
            encrypt("hello", None)  # type: ignore[arg-type]

    def test_decrypt_none_key_raises_type_error(self) -> None:
        """decrypt(ciphertext, None) must raise TypeError."""
        ciphertext = encrypt("hello", TEST_KEY)
        with pytest.raises(TypeError):
            decrypt(ciphertext, None)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Tampered / malformed ciphertext
# ---------------------------------------------------------------------------


class TestTamperedCiphertext:
    """Decrypting corrupted data must raise DecryptionError."""

    def test_decrypt_invalid_base64_raises_error(self) -> None:
        """Non-base64 input must raise DecryptionError."""
        with pytest.raises(DecryptionError):
            decrypt("not-valid-base64!!!", TEST_KEY)

    def test_decrypt_truncated_ciphertext_raises_error(self) -> None:
        """Ciphertext shorter than nonce size must raise DecryptionError."""
        # base64-encode fewer than 12 bytes (the nonce size)
        short_data = base64.b64encode(b"short").decode()
        with pytest.raises(DecryptionError):
            decrypt(short_data, TEST_KEY)

    def test_decrypt_tampered_ciphertext_raises_error(self) -> None:
        """Flipping a byte in the ciphertext must fail authentication."""
        ciphertext = encrypt("secret data", TEST_KEY)
        raw = bytearray(base64.b64decode(ciphertext))
        # Flip a byte in the encrypted payload (after the 12-byte nonce)
        raw[12] ^= 0xFF
        tampered = base64.b64encode(bytes(raw)).decode()
        with pytest.raises(DecryptionError):
            decrypt(tampered, TEST_KEY)


# ---------------------------------------------------------------------------
# Key derivation: any-length key string works
# ---------------------------------------------------------------------------


class TestKeyDerivation:
    """Keys of various lengths must work (SHA-256 hashed to 32 bytes)."""

    def test_short_key_works(self) -> None:
        """A short key (< 32 bytes) must still encrypt/decrypt correctly."""
        short_key = "abc"
        ct = encrypt("payload", short_key)
        assert decrypt(ct, short_key) == "payload"

    def test_long_key_works(self) -> None:
        """A long key (> 32 bytes) must still encrypt/decrypt correctly."""
        long_key = "x" * 200
        ct = encrypt("payload", long_key)
        assert decrypt(ct, long_key) == "payload"

    def test_exact_32_byte_key_works(self) -> None:
        """A key that is exactly 32 bytes must work without hashing issues."""
        exact_key = "a" * 32
        ct = encrypt("payload", exact_key)
        assert decrypt(ct, exact_key) == "payload"
