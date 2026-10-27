"""
Integration tests for the PostgreSQL linked-item store.

These need a real database and are skipped unless TEST_DATABASE_URL points at one
(a throwaway Postgres), so the default `pytest` run and CI stay green without a DB:

    TEST_DATABASE_URL=postgresql://localhost/finance_radar_test pytest tests/test_store.py

The in-memory store, which has no external dependency, is always tested.
"""

import os
import uuid

import pytest

from services.store import MemoryLinkedItemStore, PostgresLinkedItemStore
from services.crypto import TokenCipher, generate_key

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")


def test_memory_store_returns_latest_token():
    store = MemoryLinkedItemStore()
    assert store.get_current_token() is None
    store.save_item("item-1", "token-a")
    store.save_item("item-2", "token-b")
    assert store.get_current_token() == "token-b"


@pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL not set")
def test_postgres_store_encrypts_and_roundtrips():
    cipher = TokenCipher(generate_key())
    store = PostgresLinkedItemStore(TEST_DATABASE_URL, cipher)
    store.init_schema()

    item_id = f"item-{uuid.uuid4()}"
    token = "access-sandbox-abc123"
    store.save_item(item_id, token, institution_name="Test Bank")

    # The decrypted token round-trips...
    assert store.get_current_token() == token

    # ...but the column holds ciphertext, never the raw token.
    import psycopg

    with psycopg.connect(TEST_DATABASE_URL) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT access_token_encrypted FROM linked_items WHERE item_id = %s;",
            (item_id,),
        )
        stored = cur.fetchone()[0]
    assert token not in stored
    assert cipher.decrypt(stored) == token
