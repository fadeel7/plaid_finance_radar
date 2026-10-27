"""
Symmetric encryption for secrets at rest.

The Plaid access token is the one credential that can read someone's financial
data, so it is never stored in plaintext. It is encrypted with Fernet
(AES-128-CBC + HMAC-SHA256, authenticated) before it touches the database and
decrypted only in server memory when a Plaid request is made.

The key lives in the APP_ENCRYPTION_KEY environment variable, never in the
repo or the database. Generate one with:

    python -m services.crypto

`cryptography` is imported lazily so demo mode (no persistence) needs neither
the dependency nor a key.
"""

from __future__ import annotations


class TokenCipher:
    """Encrypt/decrypt short secrets (access tokens) with a Fernet key."""

    def __init__(self, key: str):
        if not key:
            raise RuntimeError(
                "APP_ENCRYPTION_KEY is required to store access tokens. "
                "Generate one with: python -m services.crypto"
            )
        from cryptography.fernet import Fernet

        # Fernet validates the key format (urlsafe base64, 32 bytes) and raises
        # a clear error if it is malformed.
        self._fernet = Fernet(key.encode() if isinstance(key, str) else key)

    def encrypt(self, plaintext: str) -> str:
        """Return the ciphertext as a storable string. A fresh random IV is used
        each call, so the same token encrypts to different ciphertext every time."""
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        """Return the original plaintext. Raises cryptography.fernet.InvalidToken
        if the ciphertext was tampered with or the key is wrong."""
        return self._fernet.decrypt(ciphertext.encode()).decode()


def generate_key() -> str:
    """Generate a new Fernet key suitable for APP_ENCRYPTION_KEY."""
    from cryptography.fernet import Fernet

    return Fernet.generate_key().decode()


if __name__ == "__main__":
    # Convenience: `python -m services.crypto` prints a fresh key to paste into .env
    print(generate_key())
