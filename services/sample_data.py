"""
Realistic synthetic transactions for demo mode.

This lets the whole app — detection, categorization, dashboard — run with zero setup
and no Plaid keys, which means anyone can clone the repo and see it work in seconds.
The data is deliberately messy on purpose: descriptions carry trailing digits and
store numbers, amounts drift a few cents, and dates wobble, so the recurring detector
is doing real work rather than matching perfect inputs.
"""

from __future__ import annotations

import random
from datetime import date, timedelta

random.seed(7)  # deterministic, so the demo looks the same every run

_TODAY = date.today()


def _jitter_amount(base: float, pct: float = 0.0) -> float:
    if pct == 0:
        return round(base, 2)
    delta = base * pct * random.uniform(-1, 1)
    return round(base + delta, 2)


def _recurring_series(name, base_amount, every_days, months_back, amt_jitter=0.0):
    """Emit a charge every `every_days`, with small date/amount wobble."""
    out = []
    d = _TODAY - timedelta(days=months_back * 30)
    while d <= _TODAY:
        wobble = timedelta(days=random.randint(-1, 1))
        suffix = f" {random.randint(1000, 9999)}" if random.random() < 0.5 else ""
        out.append({
            "date": (d + wobble).isoformat(),
            "amount": _jitter_amount(base_amount, amt_jitter),
            "name": name + suffix,
        })
        d += timedelta(days=every_days)
    return out


def _random_spending(names, lo, hi, count, months_back):
    out = []
    for _ in range(count):
        d = _TODAY - timedelta(days=random.randint(0, months_back * 30))
        out.append({
            "date": d.isoformat(),
            "amount": -round(random.uniform(lo, hi), 2),
            "name": random.choice(names),
        })
    return out


def sample_transactions() -> list[dict]:
    """A ~6 month history for one fictional account. Amount sign convention:
    positive = money in, negative = money out."""
    txns: list[dict] = []

    # Recurring income — biweekly salary
    txns += _recurring_series("ACME CORP PAYROLL DIRECT DEP", 2100.00, 14, 6)

    # Recurring expenses — the subscriptions the detector should catch
    txns += _recurring_series("Rent - Oakmont Properties", -1450.00, 30, 6)
    txns += _recurring_series("NETFLIX.COM", -15.49, 30, 6)
    txns += _recurring_series("Spotify USA", -11.99, 30, 6)
    txns += _recurring_series("Planet Fitness", -24.99, 30, 6)
    txns += _recurring_series("Comcast Internet", -79.99, 30, 6, amt_jitter=0.02)
    txns += _recurring_series("Verizon Wireless", -85.00, 30, 6, amt_jitter=0.03)
    txns += _recurring_series("AMAZON PRIME", -14.99, 30, 6)
    txns += _recurring_series("Adobe Creative Cloud", -54.99, 30, 6)

    # Irregular, non-recurring spending — noise the detector must ignore
    txns += _random_spending(["Starbucks", "Blue Bottle Coffee", "Chipotle", "McDonald's"], 4, 18, 40, 6)
    txns += _random_spending(["Whole Foods Market", "Trader Joe's", "Safeway"], 25, 120, 24, 6)
    txns += _random_spending(["Uber", "Lyft", "Shell Gas", "Chevron"], 8, 55, 22, 6)
    txns += _random_spending(["Amazon", "Target", "Walmart"], 10, 160, 18, 6)

    txns.sort(key=lambda t: t["date"], reverse=True)
    return txns
