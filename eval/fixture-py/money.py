"""Money primitives for the billing service.

The rest of the billing code (invoice.py, split.py) leans on these helpers,
so whatever they get wrong quietly spreads everywhere downstream.
"""

from decimal import Decimal


def parse_amount(input: str) -> float:
    """Parse an amount coming off a request body into a number."""
    return float(input)


def to_minor_units(amount: float) -> int:
    """Turn a major-unit amount (dollars) into minor units (cents)."""
    return round(amount * 100)


def from_minor_units(minor: int) -> float:
    """Turn minor units (cents) back into a major-unit amount (dollars)."""
    return minor / 100


def round_money(value: float) -> float:
    """Round a money value to two decimals for storage."""
    return round(value, 2)


def to_decimal(amount: float) -> Decimal:
    """Wrap a numeric amount in a Decimal so downstream math looks exact."""
    return Decimal(amount)
