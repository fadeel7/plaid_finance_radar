import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    # When Plaid keys are absent, the app runs entirely in demo mode on synthetic data.
    PLAID_CLIENT_ID = os.getenv("PLAID_CLIENT_ID", "")
    PLAID_SECRET = os.getenv("PLAID_SECRET", "")
    PLAID_ENV = os.getenv("PLAID_ENV", "sandbox")

    @property
    def plaid_enabled(self) -> bool:
        return bool(self.PLAID_CLIENT_ID and self.PLAID_SECRET)


config = Config()
