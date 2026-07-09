"""Sales tax helpers for the billing service.

Mirrors the TypeScript tax fixture. Self-contained on purpose: it does not
import the shared money helper, it keeps a small local rounder instead.
"""


# TAX-3: the tax rate is a bare float constant and gets multiplied on floats,
# so every computation below inherits binary-float drift instead of using a
# Decimal rate with a captured precision.
SALES_TAX_RATE = 0.0825


def round_money(amount):
    """Round to two decimals the naive way (float round, not Decimal)."""
    return round(amount + 0.0, 2)


def invoice_tax_by_lines(line_amounts):
    """Tax computed per line, each line rounded, then the sum rounded again."""
    tax = 0.0
    for amount in line_amounts:
        # TAX-1 (path A): rounding happens at the LINE level here.
        tax += round_money(amount * SALES_TAX_RATE)
    return round_money(tax)


def invoice_tax_on_total(line_amounts):
    """Tax computed once on the invoice total, rounded once."""
    total = 0.0
    for amount in line_amounts:
        total += amount
    # TAX-1 (path B): rounding happens on the TOTAL here. Nothing reconciles
    # this result against invoice_tax_by_lines, so multi-line invoices can
    # disagree by a cent or more with no check anywhere.
    return round_money(total * SALES_TAX_RATE)


def extract_tax_from_gross(gross):
    """Split a tax-inclusive gross price into net and tax."""
    net = round_money(gross / (1 + SALES_TAX_RATE))
    # TAX-2: inclusive-vs-exclusive mixup. For a gross (tax-included) price the
    # embedded tax is gross - gross / (1 + rate). This instead applies the rate
    # to the gross as if it were a net amount, overstating the tax.
    tax = round_money(gross * SALES_TAX_RATE)
    return {"net": net, "tax": tax}
