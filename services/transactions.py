"""
Transaction sources.

The rest of the app (detection, categorization, cash flow) never knows or cares
where transactions came from — it only sees a normalized list of dicts with the
keys date / amount / name / category. This is the adapter pattern: two sources,
one shape. Demo mode uses synthetic data; Plaid mode pulls from the sandbox. Adding
a third source later (a CSV import, a different aggregator) means writing one class,
not touching the analysis code.

Amount sign convention used everywhere downstream:
    positive = money IN (income),  negative = money OUT (expense).
Plaid's own convention is the opposite (positive = outflow), so PlaidSource flips it.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from services.sample_data import sample_transactions


class TransactionSource(ABC):
    @abstractmethod
    def fetch(self) -> list[dict]:
        ...


class SampleSource(TransactionSource):
    """Deterministic synthetic data — no network, no keys."""

    def fetch(self) -> list[dict]:
        return sample_transactions()


class PlaidSource(TransactionSource):
    """Pulls real transactions from the Plaid sandbox.

    Kept import-light so the app runs in demo mode even if the Plaid SDK isn't
    installed. The access token is passed in by the caller and never leaves the
    server — the browser only ever holds a short-lived public token during linking.
    """

    def __init__(self, client, access_token: str, days: int = 180):
        self._client = client
        self._access_token = access_token
        self._days = days

    def fetch(self) -> list[dict]:
        from datetime import date, timedelta
        from plaid.model.transactions_get_request import TransactionsGetRequest
        from plaid.model.transactions_get_request_options import TransactionsGetRequestOptions

        end = date.today()
        start = end - timedelta(days=self._days)

        acc: list[dict] = []
        offset = 0
        while True:
            req = TransactionsGetRequest(
                access_token=self._access_token,
                start_date=start,
                end_date=end,
                options=TransactionsGetRequestOptions(count=250, offset=offset),
            )
            resp = self._client.transactions_get(req)
            for t in resp["transactions"]:
                acc.append({
                    "date": t["date"].isoformat() if hasattr(t["date"], "isoformat") else str(t["date"]),
                    "amount": -float(t["amount"]),  # flip to our convention
                    "name": t.get("merchant_name") or t["name"],
                    "category": (t.get("personal_finance_category") or {}).get("primary"),
                })
            if len(acc) >= resp["total_transactions"]:
                break
            offset = len(acc)
        return acc
