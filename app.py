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
from services.store import build_store
from analysis.recurring import detect_recurring
from analysis.categorize import spending_by_category
from analysis.cashflow import monthly_cashflow, projection

app = Flask(__name__)

# Where linked Plaid items live. With DATABASE_URL set this is PostgreSQL with the
# access token encrypted at rest; otherwise an in-memory store so demo mode needs no
# setup. Either way the token stays server-side and never reaches the browser.
store = build_store(config)


def current_source():
    """Pick the active transaction source. A linked Plaid item wins; otherwise demo."""
    token = store.get_current_token() if config.plaid_enabled else None
    if token:
        from services.plaid_client import build_client
        return PlaidSource(build_client(config), token)
    return SampleSource()


def build_overview(transactions: list[dict], mode: str) -> dict:
    recurring = detect_recurring(transactions)
    subs = [r for r in recurring if r.kind == "expense"]
    monthly_sub_cost = round(sum(r.monthly_cost for r in subs), 2)

    # A rough starting balance so the projection has somewhere to begin.
    starting_balance = round(sum(t["amount"] for t in transactions), 2)

    return {
        "mode": mode,
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
    source = current_source()
    mode = "plaid" if isinstance(source, PlaidSource) else "demo"
    return jsonify(build_overview(source.fetch(), mode))


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
    access_token, item_id = exchange_public_token(build_client(config), public_token)
    store.save_item(item_id, access_token)
    return jsonify({"linked": True})


if __name__ == "__main__":
    # Create the linked_items table on first run when persistence is configured.
    if config.persistence_enabled:
        store.init_schema()
    port = int(__import__("os").getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=True)
