\
\
\
\
\
\

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
\
\
\
\
\
\
\


    amount = money.round_money(money.from_minor_units(minor, currency), currency)
    return {"amount": str(amount), "currency": currency}


def invoice_response(invoice: InvoiceRecord) -> str:
    \
    return json.dumps(
        {"id": invoice.id, "total": money_json(invoice.total_minor, invoice.currency)}
    )


def account_balance_response(balance_minor: int, currency: str) -> str:
    \
    return json.dumps({"balance": money_json(balance_minor, currency)})


def parse_payment_request(body: str) -> dict:
    \
    parsed = json.loads(body)
    return {
        "amount": money.parse_amount(parsed["amount"]),
        "currency": parsed["currency"],
    }
