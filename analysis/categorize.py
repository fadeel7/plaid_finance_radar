"""
Spending categorization.

When transactions come from Plaid they carry a category already, so we use it. In
demo mode (and as a fallback for anything uncategorized) we map the merchant name
to a bucket with keyword rules. Keeping this in one place means the dashboard always
has clean, consistent buckets regardless of where the data came from.
"""

from __future__ import annotations

# keyword -> bucket. First match wins.
_RULES = [
    (("rent", "landlord", "property", "apartment"), "Housing"),
    (("netflix", "spotify", "hulu", "disney", "youtube", "prime video", "hbo"), "Subscriptions"),
    (("gym", "fitness", "planet", "peloton"), "Health & Fitness"),
    (("uber", "lyft", "gas", "shell", "exxon", "chevron", "transit", "parking"), "Transport"),
    (("whole foods", "trader", "grocery", "safeway", "kroger", "aldi", "market"), "Groceries"),
    (("starbucks", "coffee", "chipotle", "mcdonald", "restaurant", "doordash", "grubhub", "cafe"), "Dining"),
    (("electric", "water", "utility", "comcast", "verizon", "at&t", "internet", "phone"), "Utilities"),
    (("amazon", "target", "walmart", "store", "shop"), "Shopping"),
    (("salary", "payroll", "deposit", "direct dep"), "Income"),
]


def categorize(name: str, plaid_category: str | None = None) -> str:
    if plaid_category:
        return plaid_category
    low = name.lower()
    for keywords, bucket in _RULES:
        if any(k in low for k in keywords):
            return bucket
    return "Other"


def spending_by_category(transactions: list[dict]) -> list[dict]:
    """Aggregate outflows into category totals, largest first."""
    totals: dict[str, float] = {}
    for t in transactions:
        if t["amount"] >= 0:
            continue  # income is handled separately
        bucket = categorize(t["name"], t.get("category"))
        totals[bucket] = totals.get(bucket, 0.0) + abs(t["amount"])
    rows = [{"category": k, "total": round(v, 2)} for k, v in totals.items()]
    rows.sort(key=lambda r: r["total"], reverse=True)
    return rows
