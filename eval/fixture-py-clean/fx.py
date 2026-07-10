"""Currency conversion and settlement (correct twin of fixture-py/fx.py).

Rates are immutable and carry a source and timestamp, converted amounts record
which rate was applied, settlement keeps the original billed amount, and sums
refuse to add across currencies.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

import money


@dataclass(frozen=True)
class Rate:
    """A rate quote with provenance, so a conversion can always be audited.

    Correct counterpart of FX-2: the rate is not a bare mutable dict value; it
    carries its pair, its source, and the instant it was fetched.
    """

    pair: str
    value: Decimal
    source: str
    fetched_at: datetime


@dataclass(frozen=True)
class Converted:
    """The result of a conversion, tagged with the exact rate that produced it."""

    amount: Decimal
    currency: str
    rate: Rate


# An immutable snapshot of rates. A real service loads these from a provider with
# a timestamp; frozen here so no runtime mutation can silently change a later
# conversion (FX-2 corrected).
_RATES: dict[str, Rate] = {
    "USD:EUR": Rate(
        "USD:EUR", Decimal("0.92"), "ecb", datetime(2026, 1, 1, tzinfo=timezone.utc)
    ),
    "USD:MXN": Rate(
        "USD:MXN", Decimal("18.70"), "ecb", datetime(2026, 1, 1, tzinfo=timezone.utc)
    ),
}


def get_rate(from_currency: str, to_currency: str) -> Rate:
    """Look up a rate, deriving the inverse from the single stored direction.

    Correct counterpart of FX-1: the reverse rate is 1 / forward, computed from
    the one stored quote, so a convert-and-convert-back uses reciprocal rates and
    does not drift the way two independently rounded rates would.
    """
    pair = f"{from_currency}:{to_currency}"
    if pair in _RATES:
        return _RATES[pair]
    inverse_pair = f"{to_currency}:{from_currency}"
    if inverse_pair in _RATES:
        forward = _RATES[inverse_pair]
        return Rate(
            pair, Decimal(1) / forward.value, forward.source, forward.fetched_at
        )
    raise ValueError(f"no rate for {pair}")


def convert(amount: Decimal, from_currency: str, to_currency: str) -> Converted:
    """Convert an amount, returning the value tagged with the rate applied."""
    if from_currency == to_currency:
        return Converted(
            amount,
            to_currency,
            Rate(
                f"{to_currency}:{to_currency}",
                Decimal(1),
                "identity",
                datetime(2026, 1, 1, tzinfo=timezone.utc),
            ),
        )
    rate = get_rate(from_currency, to_currency)
    converted = money.round_money(amount * rate.value, to_currency)
    return Converted(converted, to_currency, rate)


def settle_invoice(invoice: dict, payout_currency: str) -> dict:
    """Settle an invoice into the payout currency without losing the original.

    Correct counterpart of FX-3: the original billed amount and currency are kept
    (billed_total, billed_currency); the settled figures are added alongside, so
    a later refund or audit can still recover what was actually billed.
    """
    result = convert(invoice["total"], invoice["currency"], payout_currency)
    return {
        **invoice,
        "billed_total": invoice["total"],
        "billed_currency": invoice["currency"],
        "settled_total": result.amount,
        "settled_currency": payout_currency,
        "settlement_rate": result.rate.value,
    }


def total_revenue(invoices: list[dict], reporting_currency: str) -> Converted:
    """Sum invoice totals, converting each into one reporting currency first.

    Correct counterpart of FX-4: amounts are never added across currencies. Each
    invoice is converted into the reporting currency before it joins the sum, so
    the result is a single well-defined amount in a stated unit.
    """
    total = Decimal(0)
    latest_rate: Rate | None = None
    for invoice in invoices:
        converted = convert(invoice["total"], invoice["currency"], reporting_currency)
        total += converted.amount
        latest_rate = converted.rate
    if latest_rate is None:
        raise ValueError("no invoices to total")
    return Converted(total, reporting_currency, latest_rate)
