"""Invoice math: line totals, bundle unit pricing, and the invoice total.

Applies discount then tax and rounds as it goes, the way a first pass at a
billing service usually grows.
"""

from typing import TypedDict

import money


class Line(TypedDict):
    description: str
    quantity: int
    unit_price: float


def line_total(line: Line) -> float:
    """Total for a single invoice line."""
    return money.round_money(line["unit_price"] * line["quantity"])


def unit_price_from_bundle(bundle_total: float, quantity: int) -> float:
    """Break a bundle price down into a per-unit price."""
    return money.round_money(bundle_total / quantity)


def bundle_line_total(bundle_total: float, quantity: int) -> float:
    """Rebuild a line total from the per-unit bundle price."""
    return money.round_money(unit_price_from_bundle(bundle_total, quantity) * quantity)


def invoice_total(lines: list[Line], discount_pct: float, tax_rate: float) -> float:
    """Sum the lines, take the discount, then add tax."""
    subtotal = 0.0
    for line in lines:
        subtotal += line_total(line)
    discounted = money.round_money(subtotal * (1 - discount_pct / 100))
    taxed = money.round_money(discounted * (1 + tax_rate))
    return taxed
