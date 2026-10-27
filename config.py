import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    # When Plaid keys are absent, the app runs entirely in demo mode on synthetic data.
    PLAID_CLIENT_ID = os.getenv("PLAID_CLIENT_ID", "")
    PLAID_SECRET = os.getenv("PLAID_SECRET", "")
    PLAID_ENV = os.getenv("PLAID_ENV", "sandbox")

    # Persistence is optional. With no DATABASE_URL the app keeps linked items in
    # memory (demo mode). APP_ENCRYPTION_KEY encrypts access tokens at rest and is
    # only needed when a database is configured — generate one with
    # `python -m services.crypto`.
    DATABASE_URL = os.getenv("DATABASE_URL", "")
    APP_ENCRYPTION_KEY = os.getenv("APP_ENCRYPTION_KEY", "")

    @property
    def plaid_enabled(self) -> bool:
        return bool(self.PLAID_CLIENT_ID and self.PLAID_SECRET)

    @property
    def database_url(self) -> str:
        return self.DATABASE_URL

    @property
    def encryption_key(self) -> str:
        return self.APP_ENCRYPTION_KEY

    @property
    def persistence_enabled(self) -> bool:
        return bool(self.DATABASE_URL)


config = Config()
