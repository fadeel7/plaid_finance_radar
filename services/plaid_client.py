"""
Thin wrapper around the Plaid client and the Link token flow.

Security note that matters for the interview story: the browser never sees the
access token. The flow is:
    1. Server creates a short-lived *link token* and hands it to the browser.
    2. The user links their bank in Plaid Link; the browser gets a *public token*.
    3. The browser sends that public token back; the server exchanges it for the
       long-lived *access token* and keeps it server-side only.
The access token is the sensitive credential — it can read someone's financial
data — so it is created, stored, and used exclusively on the server.
"""

from __future__ import annotations


def build_client(config):
    """Construct a configured Plaid API client. Imported lazily so demo mode
    works without the Plaid SDK installed."""
    import plaid
    from plaid.api import plaid_api

    host = {
        "sandbox": plaid.Environment.Sandbox,
        "production": plaid.Environment.Production,
    }.get(config.PLAID_ENV, plaid.Environment.Sandbox)

    configuration = plaid.Configuration(
        host=host,
        api_key={"clientId": config.PLAID_CLIENT_ID, "secret": config.PLAID_SECRET},
    )
    return plaid_api.PlaidApi(plaid.ApiClient(configuration))


def create_link_token(client, user_id: str = "demo-user"):
    from plaid.model.link_token_create_request import LinkTokenCreateRequest
    from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
    from plaid.model.products import Products
    from plaid.model.country_code import CountryCode

    req = LinkTokenCreateRequest(
        user=LinkTokenCreateRequestUser(client_user_id=user_id),
        client_name="Finance Radar",
        products=[Products("transactions")],
        country_codes=[CountryCode("US")],
        language="en",
    )
    return client.link_token_create(req)["link_token"]


def exchange_public_token(client, public_token: str) -> str:
    from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest

    req = ItemPublicTokenExchangeRequest(public_token=public_token)
    return client.item_public_token_exchange(req)["access_token"]
