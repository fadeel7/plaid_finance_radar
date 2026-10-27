"""Tests for at-rest token encryption. No database required."""

import pytest

from services.crypto import TokenCipher, generate_key

TOKEN = "access-sandbox-11111111-2222-3333-4444-555555555555"


def test_roundtrip_recovers_plaintext():
    cipher = TokenCipher(generate_key())
    encrypted = cipher.encrypt(TOKEN)
    assert encrypted != TOKEN
    assert cipher.decrypt(encrypted) == TOKEN


def test_ciphertext_is_randomized_each_call():
    # Fernet uses a fresh IV, so the same token never produces identical ciphertext.
    cipher = TokenCipher(generate_key())
    assert cipher.encrypt(TOKEN) != cipher.encrypt(TOKEN)


def test_wrong_key_cannot_decrypt():
    from cryptography.fernet import InvalidToken

    encrypted = TokenCipher(generate_key()).encrypt(TOKEN)
    with pytest.raises(InvalidToken):
        TokenCipher(generate_key()).decrypt(encrypted)


def test_missing_key_raises():
    with pytest.raises(RuntimeError):
        TokenCipher("")
