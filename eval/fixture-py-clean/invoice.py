"""Invoice math (correct twin of fixture-py/invoice.py).

Decimal throughout, unrounded intermediates, and a single final rounding step so
order does not get baked into the total. Bundle pricing multiplies before it
divides, so no per-unit rounding error is amplified back up by the quantity.
"""

from decimal import Decimal
from typing import TypedDict

import money


class Line(TypedDict):
    description: str
    quantity: int
    unit_price: Decimal


def line_total(line: Line) -> Decimal:
    """Total for a single invoice line (kept unrounded until the invoice total)."""
    return line["unit_price"] * line["quantity"]


def bundle_line_total(bundle_total: Decimal, quantity: int) -> Decimal:
    """Rebuild a line total from a bundle price.

    Correct counterpart of ROU-4: a bundle total IS the line total for the whole
    quantity, so there is nothing to divide-then-multiply. No intermediate
    per-unit figure is rounded and multiplied back up.
    """
    return bundle_total


def unit_price_from_bundle(bundle_total: Decimal, quantity: int) -> Decimal:
    """Break a bundle price into a per-unit price for display only.

    This is a display helper, not a step in the invoice total, so rounding it is
    fine: the authoritative total uses bundle_line_total, which never divides.
    """
    return money.round_money(bundle_total / quantity)


def invoice_total(
    lines: list[Line], discount_pct: Decimal, tax_rate: Decimal
) -> Decimal:
    """Sum the lines, take the discount, add tax, round ONCE at the end.

    Correct counterpart of ROU-3: every intermediate (subtotal, discounted,
    taxed) stays a full-precision Decimal; only the returned total is rounded, so
    the order of operations is not frozen into a chain of pre-rounded steps.
    """
    subtotal = Decimal(0)
    for line in lines:
        subtotal += line_total(line)
    discounted = subtotal * (Decimal(1) - discount_pct / Decimal(100))
    taxed = discounted * (Decimal(1) + tax_rate)
    return money.round_money(taxed)
