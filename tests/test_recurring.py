"""
Tests for the recurring-charge detector.

These pin down the behavior that actually matters: a clean monthly subscription is
caught, irregular one-off spending is not, merchant names with trailing noise still
group together, and amounts/dates that wobble within tolerance don't break detection.
"""

from datetime import date, timedelta

from analysis.recurring import detect_recurring, normalize_merchant


def _monthly(name, amount, months, start_days_ago=180):
    """Build a monthly series of `months` charges."""
    today = date.today()
    out = []
    d = today - timedelta(days=start_days_ago)
    for _ in range(months):
        out.append({"date": d.isoformat(), "amount": amount, "name": name})
        d += timedelta(days=30)
    return out


def test_normalize_merchant_strips_noise_and_digits():
    assert normalize_merchant("NETFLIX.COM 8899") == "netflix"
    assert normalize_merchant("Netflix.com") == "netflix"
    assert normalize_merchant("SPOTIFY USA 123") == "spotify usa"


def test_detects_clean_monthly_subscription():
    txns = _monthly("NETFLIX.COM", -15.49, 6)
    found = detect_recurring(txns)
    assert len(found) == 1
    sub = found[0]
    assert sub.cadence == "monthly"
    assert sub.kind == "expense"
    assert sub.occurrences == 6
    assert sub.confidence >= 0.62


def test_ignores_irregular_one_off_spending():
    # Same merchant, but random dates and amounts — not a subscription.
    today = date.today()
    txns = [
        {"date": (today - timedelta(days=3)).isoformat(), "amount": -12.0, "name": "Chipotle"},
        {"date": (today - timedelta(days=19)).isoformat(), "amount": -8.5, "name": "Chipotle"},
        {"date": (today - timedelta(days=52)).isoformat(), "amount": -22.0, "name": "Chipotle"},
        {"date": (today - timedelta(days=61)).isoformat(), "amount": -6.0, "name": "Chipotle"},
    ]
    found = detect_recurring(txns)
    assert found == []


def test_groups_noisy_names_together():
    today = date.today()
    txns = []
    d = today - timedelta(days=150)
    for i in range(5):
        txns.append({"date": d.isoformat(), "amount": -11.99, "name": f"NETFLIX.COM {1000 + i}"})
        d += timedelta(days=30)
    found = detect_recurring(txns)
    assert len(found) == 1
    assert found[0].occurrences == 5


def test_detects_recurring_income_as_income():
    txns = _monthly("ACME PAYROLL", 2100.0, 6)
    found = detect_recurring(txns)
    assert len(found) == 1
    assert found[0].kind == "income"


def test_requires_minimum_occurrences():
    txns = _monthly("NETFLIX.COM", -15.49, 2)  # only two charges
    assert detect_recurring(txns) == []


def test_tolerates_small_amount_and_date_wobble():
    today = date.today()
    txns = []
    d = today - timedelta(days=180)
    amounts = [-79.99, -80.49, -79.50, -80.10, -79.99, -80.25]
    for amt in amounts:
        txns.append({"date": d.isoformat(), "amount": amt, "name": "Comcast Internet"})
        d += timedelta(days=30 + (1 if amt < -80 else -1))  # wobble the gap
    found = detect_recurring(txns)
    assert len(found) == 1
    assert found[0].cadence == "monthly"
