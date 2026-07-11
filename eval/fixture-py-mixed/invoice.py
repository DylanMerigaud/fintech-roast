\
\
\
\
\
\

from decimal import Decimal
from typing import TypedDict

import money


class Line(TypedDict):
    description: str
    quantity: int
    unit_price: Decimal


def line_total(line: Line) -> Decimal:
    \
    return line["unit_price"] * line["quantity"]


def bundle_line_total(bundle_total: Decimal, quantity: int) -> Decimal:
    \
\
\
\
\
\
    return bundle_total


def unit_price_from_bundle(bundle_total: Decimal, quantity: int) -> Decimal:
    \
\
\
\
\
    return money.round_money(bundle_total / quantity)


def invoice_total(
    lines: list[Line], discount_pct: Decimal, tax_rate: Decimal
) -> Decimal:
    \
\
\
\
\
\
    subtotal = Decimal(0)
    for line in lines:
        subtotal += line_total(line)
    discounted = subtotal * (Decimal(1) - discount_pct / Decimal(100))
    taxed = discounted * (Decimal(1) + tax_rate)
    return money.round_money(taxed)
