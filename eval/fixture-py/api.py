"""JSON API surface for the billing service.

The response builders a set of read endpoints would return. Plain functions
returning JSON strings, standing in for Flask/FastAPI view returns. Mirrors the
TypeScript api.ts.
"""

import json
from dataclasses import dataclass

from money import from_minor_units, parse_amount


@dataclass
class InvoiceRecord:
    id: str
    total_cents: int
    currency: str


def invoice_response(invoice: InvoiceRecord) -> str:
    """Serialize an invoice for the GET /invoices/:id endpoint.

    API-1: the total is emitted as a bare JSON number (a float, via
    from_minor_units) rather than a decimal string or a minor-unit integer, and
    the invoice's currency is dropped from the payload entirely, so the client
    gets an amount with no unit and a value that has round-tripped through binary
    floating point.
    """
    return json.dumps({"id": invoice.id, "total": from_minor_units(invoice.total_cents)})


def account_balance_response(balance_cents: int) -> str:
    """Serialize an account balance for the GET /accounts/:id/balance endpoint.

    API-4: this endpoint returns the amount as an integer number of cents, while
    invoice_response above returns decimal dollars for the same kind of money
    value. Two endpoints in one API disagree on the unit, with no canonical
    money shape, so a consumer that reads both has to guess which is which.
    """
    return json.dumps({"balance": balance_cents})


def parse_payment_request(body: str) -> dict:
    """Parse an inbound payment request body from the POST /payments endpoint."""
    parsed = json.loads(body)
    return {"amount": parse_amount(parsed["amount"])}
