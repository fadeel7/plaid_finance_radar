"""
Recurring-charge detection.

This is the core of the project. Given a flat list of transactions, it finds the
ones that repeat on a schedule — subscriptions, rent, salary — without being told
in advance what to look for. Bank transaction descriptions are messy ("NETFLIX.COM
8899", "Netflix 1-888..."), amounts drift a few cents, and dates wobble by a day or
two, so the detector has to be tolerant without being gullible.

The approach, per merchant:
  1. Normalize the description so the same merchant collapses to one key.
  2. Look at the gaps between charges and see if they cluster around a known cadence
     (weekly / biweekly / monthly / quarterly / yearly).
  3. Score three independent signals — how regular the interval is, how consistent
     the amount is, and how many times it has occurred — and combine them into a
     single confidence score.
  4. Keep it only if a cadence matched and confidence clears a threshold, then
     predict the next charge date and normalize the cost to a monthly figure.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from datetime import date, timedelta
from statistics import median, pstdev

# name, expected gap (days), tolerance (days), charges-per-month factor
CADENCES = [
    ("weekly", 7, 2, 4.345),
    ("biweekly", 14, 3, 2.172),
    ("monthly", 30, 5, 1.0),
    ("quarterly", 91, 12, 1 / 3),
    ("yearly", 365, 20, 1 / 12),
]

_STRIP = re.compile(r"[^a-z ]+")
_NOISE = {
    "llc", "inc", "com", "www", "payment", "pos", "purchase", "debit",
    "card", "recurring", "autopay", "bill", "online", "ach", "the",
}

CONFIDENCE_THRESHOLD = 0.62


def normalize_merchant(name: str) -> str:
    """Collapse a raw description to a stable merchant key.

    'NETFLIX.COM 8899 LOS GATOS' and 'Netflix.com' both become 'netflix'.
    """
    cleaned = _STRIP.sub(" ", name.lower())
    tokens = [t for t in cleaned.split() if len(t) > 1 and t not in _NOISE]
    return " ".join(tokens[:3]) if tokens else name.lower().strip()


@dataclass
class Recurring:
    merchant: str
    display_name: str
    cadence: str
    amount: float            # average signed amount (negative = expense)
    monthly_cost: float      # normalized to a per-month figure (absolute value)
    occurrences: int
    last_date: str
    next_date: str
    confidence: float
    kind: str                # "expense" or "income"

    def to_dict(self) -> dict:
        return asdict(self)


def _interval_score(gaps: list[int], expected: int) -> float:
    """1.0 when gaps are perfectly regular at the expected cadence, decaying as
    they scatter. Uses spread relative to the expected gap."""
    if not gaps:
        return 0.0
    spread = pstdev(gaps) if len(gaps) > 1 else 0.0
    return max(0.0, 1.0 - spread / expected)


def _amount_score(amounts: list[float]) -> float:
    """1.0 when every charge is the same amount, decaying as they vary."""
    mags = [abs(a) for a in amounts]
    avg = sum(mags) / len(mags)
    if avg == 0:
        return 0.0
    spread = pstdev(mags) if len(mags) > 1 else 0.0
    return max(0.0, 1.0 - spread / avg)


def _occurrence_score(n: int) -> float:
    """More repetitions means more certainty, saturating at six."""
    return min(1.0, n / 6.0)


def _match_cadence(median_gap: float):
    for name, expected, tol, factor in CADENCES:
        if abs(median_gap - expected) <= tol:
            return name, expected, factor
    return None


def detect_recurring(transactions: list[dict], min_occurrences: int = 3) -> list[Recurring]:
    """Return the recurring series found in `transactions`.

    Each transaction is a dict with keys: date (ISO str), amount (float, negative
    = outflow), name (str).
    """
    groups: dict[str, list[dict]] = {}
    for t in transactions:
        groups.setdefault(normalize_merchant(t["name"]), []).append(t)

    results: list[Recurring] = []
    for key, items in groups.items():
        if len(items) < min_occurrences:
            continue

        items.sort(key=lambda t: t["date"])
        dates = [date.fromisoformat(t["date"]) for t in items]
        gaps = [(dates[i] - dates[i - 1]).days for i in range(1, len(dates))]
        if not gaps:
            continue

        matched = _match_cadence(median(gaps))
        if matched is None:
            continue
        cadence, expected, factor = matched

        amounts = [t["amount"] for t in items]
        interval = _interval_score(gaps, expected)
        amount = _amount_score(amounts)
        occ = _occurrence_score(len(items))

        # Weighted: regularity of timing matters most, then amount stability.
        confidence = round(0.5 * interval + 0.3 * amount + 0.2 * occ, 3)
        if confidence < CONFIDENCE_THRESHOLD:
            continue

        avg_amount = round(sum(amounts) / len(amounts), 2)
        results.append(
            Recurring(
                merchant=key,
                display_name=items[-1]["name"],
                cadence=cadence,
                amount=avg_amount,
                monthly_cost=round(abs(avg_amount) * factor, 2),
                occurrences=len(items),
                last_date=dates[-1].isoformat(),
                next_date=(dates[-1] + timedelta(days=expected)).isoformat(),
                confidence=confidence,
                kind="income" if avg_amount > 0 else "expense",
            )
        )

    results.sort(key=lambda r: r.monthly_cost, reverse=True)
    return results
