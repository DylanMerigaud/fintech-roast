"""JSON API surface (correct twin of fixture-py/api.py).

Every money value crosses the wire in one canonical shape: a decimal-string
amount plus its ISO 4217 currency, never a bare JSON number and never a
unit-that-varies-by-endpoint.
"""

import json
from dataclasses import dataclass
from decimal import Decimal

import money


@dataclass
class InvoiceRecord:
    id: str
    total_minor: int
    currency: str


def money_json(minor: int, currency: str) -> dict:
    """The one canonical money shape returned everywhere.

    Correct counterpart of API-1 / API-4: the amount is a decimal STRING (so it
    never round-trips through a binary float in JSON) and the currency travels
    with it, and every endpoint uses this same shape so no two disagree on the
    unit.
    """
    # Round to the currency's scale so the string always shows the right number
    # of decimals (100.10, not 100.1), keeping the wire shape stable per currency.
    amount = money.round_money(money.from_minor_units(minor, currency), currency)
    return {"amount": str(amount), "currency": currency}


def invoice_response(invoice: InvoiceRecord) -> str:
    """Serialize an invoice for GET /invoices/:id using the canonical shape."""
    return json.dumps(
        {"id": invoice.id, "total": money_json(invoice.total_minor, invoice.currency)}
    )


def account_balance_response(balance_minor: int, currency: str) -> str:
    """Serialize a balance for GET /accounts/:id/balance, same canonical shape."""
    return json.dumps({"balance": money_json(balance_minor, currency)})


def parse_payment_request(body: str) -> dict:
    """Parse an inbound payment request body (amount as an exact Decimal)."""
    parsed = json.loads(body)
    return {
        "amount": money.parse_amount(parsed["amount"]),
        "currency": parsed["currency"],
    }
