"""
Persistence for linked Plaid items.

In production a linked bank item is a durable, sensitive record — it holds the
access token that can read an account. This module stores those items in
PostgreSQL with the token encrypted at rest (see services.crypto), so the raw
credential never sits in the database or reaches the browser.

Persistence is optional. With no DATABASE_URL set the app uses an in-memory
store so demo mode stays zero-setup; the Postgres driver is imported lazily and
is only needed when persistence is actually enabled. Both stores share one
interface so the rest of the app does not care which is active — the same
adapter idea used for transaction sources.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class LinkedItemStore(ABC):
    @abstractmethod
    def init_schema(self) -> None:
        """Create the backing schema if it does not exist (no-op in memory)."""

    @abstractmethod
    def save_item(self, item_id: str, access_token: str, institution_name: str | None = None) -> None:
        """Persist a linked item, encrypting the access token at rest."""

    @abstractmethod
    def get_current_token(self) -> str | None:
        """Return the most recently linked item's decrypted access token, or None."""


class MemoryLinkedItemStore(LinkedItemStore):
    """Process-memory fallback for demo mode. Holds one linked item and is lost
    on restart — which is fine, because without Plaid keys it is never used."""

    def __init__(self) -> None:
        self._token: str | None = None

    def init_schema(self) -> None:
        pass

    def save_item(self, item_id: str, access_token: str, institution_name: str | None = None) -> None:
        self._token = access_token

    def get_current_token(self) -> str | None:
        return self._token


class PostgresLinkedItemStore(LinkedItemStore):
    """Stores linked items in PostgreSQL with the access token encrypted at rest.

    Only the ciphertext column is ever written; decryption happens in memory on
    the server, right before a Plaid call. A short-lived connection is opened per
    operation, which is more than enough at this scale.
    """

    _DDL = """
    CREATE TABLE IF NOT EXISTS linked_items (
        id                     SERIAL PRIMARY KEY,
        item_id                TEXT UNIQUE NOT NULL,
        access_token_encrypted TEXT NOT NULL,
        institution_name       TEXT,
        created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at             TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    """

    def __init__(self, database_url: str, cipher) -> None:
        self._url = database_url
        self._cipher = cipher

    def _connect(self):
        import psycopg

        return psycopg.connect(self._url)

    def init_schema(self) -> None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(self._DDL)
            conn.commit()

    def save_item(self, item_id: str, access_token: str, institution_name: str | None = None) -> None:
        encrypted = self._cipher.encrypt(access_token)
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO linked_items (item_id, access_token_encrypted, institution_name)
                VALUES (%s, %s, %s)
                ON CONFLICT (item_id) DO UPDATE
                   SET access_token_encrypted = EXCLUDED.access_token_encrypted,
                       institution_name        = EXCLUDED.institution_name,
                       updated_at              = now();
                """,
                (item_id, encrypted, institution_name),
            )
            conn.commit()

    def get_current_token(self) -> str | None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT access_token_encrypted FROM linked_items ORDER BY updated_at DESC LIMIT 1;"
            )
            row = cur.fetchone()
        if not row:
            return None
        return self._cipher.decrypt(row[0])


def build_store(config) -> LinkedItemStore:
    """Return a Postgres-backed store when DATABASE_URL is set, else in-memory.

    The cipher (and therefore APP_ENCRYPTION_KEY) is only required when
    persistence is enabled.
    """
    if config.database_url:
        from services.crypto import TokenCipher

        return PostgresLinkedItemStore(config.database_url, TokenCipher(config.encryption_key))
    return MemoryLinkedItemStore()
