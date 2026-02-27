"""AES-256-GCM encryption and decryption for sensitive data (e.g. OAuth tokens).

Uses ``cryptography.hazmat.primitives.ciphers.aead.AESGCM`` with a random
12-byte nonce per encryption.  The key is derived from an arbitrary-length
string by SHA-256 hashing it to exactly 32 bytes.

Wire format (base64-encoded):
    nonce (12 bytes) || ciphertext-with-tag (variable length)
"""

import base64
import hashlib
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# Nonce length recommended by NIST SP 800-38D for AES-GCM.
_NONCE_LENGTH = 12


class DecryptionError(Exception):
    """Raised when decryption fails (wrong key, tampered data, bad format)."""


def _derive_key(key: str) -> bytes:
    """Derive a 32-byte AES-256 key from an arbitrary-length string via SHA-256."""
    return hashlib.sha256(key.encode("utf-8")).digest()


def encrypt(plaintext: str, key: str) -> str:
    """Encrypt *plaintext* with AES-256-GCM and return base64-encoded ciphertext.

    Parameters
    ----------
    plaintext:
        The string to encrypt.  May be empty but must not be ``None``.
    key:
        Encryption key of any length.  SHA-256 hashed to 32 bytes internally.

    Returns
    -------
    str
        Base64-encoded bytes: ``nonce (12B) || ciphertext+tag``.

    Raises
    ------
    TypeError
        If *plaintext* or *key* is ``None``.
    """
    if plaintext is None:
        raise TypeError("plaintext must be a str, not None")
    if key is None:
        raise TypeError("key must be a str, not None")

    derived = _derive_key(key)
    nonce = os.urandom(_NONCE_LENGTH)
    aesgcm = AESGCM(derived)
    ciphertext_with_tag = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)

    return base64.b64encode(nonce + ciphertext_with_tag).decode("ascii")


def decrypt(ciphertext: str, key: str) -> str:
    """Decrypt a base64-encoded AES-256-GCM ciphertext and return the plaintext.

    Parameters
    ----------
    ciphertext:
        Base64-encoded string produced by :func:`encrypt`.
    key:
        The same key used during encryption.

    Returns
    -------
    str
        The original plaintext.

    Raises
    ------
    TypeError
        If *ciphertext* or *key* is ``None``.
    DecryptionError
        If the ciphertext is malformed, tampered, or the key is wrong.
    """
    if ciphertext is None:
        raise TypeError("ciphertext must be a str, not None")
    if key is None:
        raise TypeError("key must be a str, not None")

    try:
        raw = base64.b64decode(ciphertext)
    except Exception as exc:
        raise DecryptionError("Decryption failed: invalid base64 encoding") from exc

    if len(raw) <= _NONCE_LENGTH:
        raise DecryptionError("Decryption failed: ciphertext too short (must be longer than nonce)")

    nonce = raw[:_NONCE_LENGTH]
    ciphertext_with_tag = raw[_NONCE_LENGTH:]

    derived = _derive_key(key)
    aesgcm = AESGCM(derived)

    try:
        plaintext_bytes = aesgcm.decrypt(nonce, ciphertext_with_tag, None)
    except Exception as exc:
        raise DecryptionError(
            "Decryption failed: authentication error (wrong key or tampered data)"
        ) from exc

    return plaintext_bytes.decode("utf-8")
