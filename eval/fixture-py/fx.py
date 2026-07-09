"""Currency conversion and settlement helpers for the billing service.

Mirrors the TypeScript fx fixture. Self-contained: no shared money import.
"""


# FX-2: the rate source is a mutable module-level dict. No value provenance,
# no source, no timestamp, no id is captured with a converted amount, so there
# is no way to know which rate was applied or when. Anyone can mutate it at
# runtime and every later conversion silently changes.
RATES = {
    "USD:EUR": 0.92,
    "EUR:USD": 1.087,
    "USD:MXN": 18.7,
    "MXN:USD": 0.0535,
}


def convert(amount, from_currency, to_currency):
    """Convert an amount from one currency to another using RATES."""
    if from_currency == to_currency:
        return amount
    rate = RATES.get(f"{from_currency}:{to_currency}")
    if rate is None:
        raise ValueError(f"no rate for {from_currency}:{to_currency}")
    # Float multiply then a naive 2-decimal round.
    return round(amount * rate, 2)


def settle_invoice(invoice, payout_currency):
    """Settle an invoice into the payout currency, in place."""
    # FX-3: the original amount and currency are OVERWRITTEN. Once settled,
    # the source-currency total is gone, so a later refund or audit cannot
    # recover what was actually billed.
    invoice["total"] = convert(invoice["total"], invoice["currency"], payout_currency)
    invoice["currency"] = payout_currency
    return invoice


def refund_in_original_currency(charged_amount, charge_currency, original_currency):
    """Refund a charge back into the currency it was originally billed in."""
    # FX-1: assumes a lossless round-trip. Converting X USD to EUR and back does
    # not return X because the two directions use independently rounded float
    # rates (0.92 and 1.087, not 1 / 0.92), so the refund drifts from the charge.
    return convert(charged_amount, charge_currency, original_currency)


def total_revenue(invoices):
    """Sum the totals of a list of invoices."""
    total = 0.0
    for invoice in invoices:
        # FX-4: adds invoice["total"] with no currency guard. USD, EUR and MXN
        # totals get summed as if they were the same unit, producing a
        # meaningless number whenever the list is mixed-currency.
        total += invoice["total"]
    return total
