"""
Finance Radar — a personal-finance API that detects recurring charges, breaks down
spending, and projects cash flow from bank transactions.

Runs in two modes behind the same API:
  - demo   (default): synthetic transactions, zero setup, no keys.
  - plaid  (when PLAID_CLIENT_ID / PLAID_SECRET are set): real Plaid sandbox data.

The analysis endpoints are identical in both modes, because everything downstream
reads a normalized transaction list from a TransactionSource — it never knows which
source produced it.
"""

from __future__ import annotations

from flask import Flask, jsonify, render_template, request

from config import config
from services.transactions import SampleSource, PlaidSource
from analysis.recurring import detect_recurring
from analysis.categorize import spending_by_category
from analysis.cashflow import monthly_cashflow, projection

app = Flask(__name__)

# In-memory store for a linked Plaid access token. In production this would be an
# encrypted per-user record in the database; here one server-side slot is enough to
# demonstrate that the token never reaches the browser.
_linked = {"access_token": None}


def current_source():
    """Pick the active transaction source. A linked Plaid item wins; otherwise demo."""
    if config.plaid_enabled and _linked["access_token"]:
        from services.plaid_client import build_client
        return PlaidSource(build_client(config), _linked["access_token"])
    return SampleSource()


def build_overview(transactions: list[dict]) -> dict:
    recurring = detect_recurring(transactions)
    subs = [r for r in recurring if r.kind == "expense"]
    monthly_sub_cost = round(sum(r.monthly_cost for r in subs), 2)

    # A rough starting balance so the projection has somewhere to begin.
    starting_balance = round(sum(t["amount"] for t in transactions), 2)

    return {
        "mode": "plaid" if (config.plaid_enabled and _linked["access_token"]) else "demo",
        "transaction_count": len(transactions),
        "headline": {
            "monthly_subscription_cost": monthly_sub_cost,
            "subscription_count": len(subs),
        },
        "subscriptions": [r.to_dict() for r in subs],
        "recurring_income": [r.to_dict() for r in recurring if r.kind == "income"],
        "spending_by_category": spending_by_category(transactions),
        "monthly_cashflow": monthly_cashflow(transactions),
        "projection": projection(recurring, starting_balance),
    }


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/overview")
def overview():
    transactions = current_source().fetch()
    return jsonify(build_overview(transactions))


@app.get("/api/health")
def health():
    return jsonify({"status": "ok", "plaid_enabled": config.plaid_enabled})


# ---- Plaid Link flow (only meaningful when Plaid keys are configured) ----

@app.post("/api/link/token")
def link_token():
    if not config.plaid_enabled:
        return jsonify({"error": "Plaid not configured — running in demo mode."}), 400
    from services.plaid_client import build_client, create_link_token
    token = create_link_token(build_client(config))
    return jsonify({"link_token": token})


@app.post("/api/link/exchange")
def link_exchange():
    if not config.plaid_enabled:
        return jsonify({"error": "Plaid not configured — running in demo mode."}), 400
    public_token = (request.get_json(silent=True) or {}).get("public_token")
    if not public_token:
        return jsonify({"error": "public_token is required"}), 400
    from services.plaid_client import build_client, exchange_public_token
    _linked["access_token"] = exchange_public_token(build_client(config), public_token)
    return jsonify({"linked": True})


if __name__ == "__main__":
    port = int(__import__("os").getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=True)
