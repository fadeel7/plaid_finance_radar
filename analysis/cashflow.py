"""
Cash-flow summary and a simple forward projection.

The projection isn't trying to be a forecasting model — it's an honest, explainable
estimate: take the recurring income and recurring expenses the detector already
found, net them into a monthly run-rate, and roll a starting balance forward. The
value is that it's built on detected recurring items, so it answers "if nothing
changes, where does my balance go?" rather than guessing.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date


def monthly_cashflow(transactions: list[dict]) -> list[dict]:
    """Income vs expenses grouped by calendar month, oldest first."""
    income: dict[str, float] = defaultdict(float)
    expense: dict[str, float] = defaultdict(float)
    for t in transactions:
        month = t["date"][:7]  # YYYY-MM
        if t["amount"] >= 0:
            income[month] += t["amount"]
        else:
            expense[month] += abs(t["amount"])

    months = sorted(set(income) | set(expense))
    return [
        {
            "month": m,
            "income": round(income[m], 2),
            "expense": round(expense[m], 2),
            "net": round(income[m] - expense[m], 2),
        }
        for m in months
    ]


def projection(recurring: list, starting_balance: float, months: int = 6) -> dict:
    """Roll `starting_balance` forward using the detected recurring run-rate."""
    monthly_income = sum(r.monthly_cost for r in recurring if r.kind == "income")
    monthly_expense = sum(r.monthly_cost for r in recurring if r.kind == "expense")
    net = round(monthly_income - monthly_expense, 2)

    balance = starting_balance
    points = [{"month": 0, "balance": round(balance, 2)}]
    for i in range(1, months + 1):
        balance += net
        points.append({"month": i, "balance": round(balance, 2)})

    return {
        "monthly_income": round(monthly_income, 2),
        "monthly_expense": round(monthly_expense, 2),
        "monthly_net": net,
        "points": points,
    }
