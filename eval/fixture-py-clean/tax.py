"""Sales tax helpers (correct twin of fixture-py/tax.py).

The rate is an exact Decimal, there is a single canonical tax path (tax on the
invoice total, rounded once), and the inclusive-price split uses the correct
gross - gross / (1 + rate) formula.
"""

from decimal import Decimal

import money

# TAX-3 corrected: the rate is an exact Decimal built from a string, not a
# binary float, so no drift enters the tax math.
SALES_TAX_RATE = Decimal("0.0825")


def invoice_tax(net_total: Decimal) -> Decimal:
    """The one canonical tax computation: tax on the net total, rounded once.

    Correct counterpart of TAX-1: there is a single tax path, so there is no
    second per-line path to disagree with. Callers that have lines sum the net
    amounts first (full precision) and call this once.
    """
    return money.round_money(net_total * SALES_TAX_RATE)


def invoice_tax_from_lines(line_amounts: list[Decimal]) -> Decimal:
    """Tax for a multi-line invoice: sum the lines exactly, then tax once.

    Same canonical path as invoice_tax; the lines are summed at full precision
    before the single rounding, so per-line and on-total agree by construction.
    """
    net_total = sum(line_amounts, Decimal(0))
    return invoice_tax(net_total)


def extract_tax_from_gross(gross: Decimal) -> dict[str, Decimal]:
    """Split a tax-inclusive gross price into net and embedded tax.

    Correct counterpart of TAX-2: the embedded tax is gross - gross / (1 + rate),
    the true inclusive formula, so net + tax reconstructs the gross exactly.
    """
    net = money.round_money(gross / (Decimal(1) + SALES_TAX_RATE))
    tax = money.round_money(gross - gross / (Decimal(1) + SALES_TAX_RATE))
    return {"net": net, "tax": tax}
