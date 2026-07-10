"""Money primitives for the billing service (correct twin of fixture-py/money.py).

Every helper here is the CORRECT counterpart of a planted bug in fixture-py:
Decimal end to end, exact construction from strings, an ISO 4217 exponent table
for minor units, and an explicit rounding mode on the one place that rounds. The
auditor should find nothing to flag here; that is the point of the clean fixture.
"""

from decimal import Decimal, ROUND_HALF_UP

# ISO 4217 minor-unit exponents for the currencies this service handles.
# JPY has 0 decimals, BHD has 3, everything else here has 2. A real service
# would load the full table; this covers the cases the tests exercise.
_MINOR_UNIT_EXPONENT = {
    "USD": 2,
    "EUR": 2,
    "MXN": 2,
    "JPY": 0,
    "BHD": 3,
}


def parse_amount(raw: str) -> Decimal:
    """Parse an amount coming off a request body into an exact Decimal.

    Correct counterpart of API-3 / STO-1: the string goes straight into Decimal,
    never through a binary float, so no inexact double is introduced at the edge.
    """
    return Decimal(raw)


def minor_unit_exponent(currency: str) -> int:
    """Return the ISO 4217 minor-unit exponent for a currency."""
    try:
        return _MINOR_UNIT_EXPONENT[currency]
    except KeyError as exc:
        raise ValueError(f"unknown currency {currency}") from exc


def to_minor_units(amount: Decimal, currency: str) -> int:
    """Turn a major-unit amount into integer minor units for its currency.

    Correct counterpart of STO-5: the scale comes from the currency's ISO 4217
    exponent, not a hardcoded *100, so JPY (0) and BHD (3) are handled right.
    """
    exponent = minor_unit_exponent(currency)
    scaled = (amount * (Decimal(10) ** exponent)).quantize(
        Decimal(1), rounding=ROUND_HALF_UP
    )
    return int(scaled)


def from_minor_units(minor: int, currency: str) -> Decimal:
    """Turn integer minor units back into a major-unit Decimal for its currency."""
    exponent = minor_unit_exponent(currency)
    return Decimal(minor) / (Decimal(10) ** exponent)


def round_money(value: Decimal, currency: str = "USD") -> Decimal:
    """Round a money value to its currency's scale with an explicit mode.

    Correct counterpart of ROU-1: the rounding mode is stated (ROUND_HALF_UP) and
    the scale is the currency's, so the result is deterministic and auditable
    rather than dependent on binary-float repr and the default banker's round.
    """
    exponent = minor_unit_exponent(currency)
    quantum = Decimal(1).scaleb(-exponent)
    return value.quantize(quantum, rounding=ROUND_HALF_UP)


def to_decimal(amount: str | int | Decimal) -> Decimal:
    """Build a Decimal from an exact source.

    Correct counterpart of STO-7: it never accepts a float. A str, int, or Decimal
    carries no binary tail, so the resulting Decimal is exact.
    """
    return Decimal(amount)
