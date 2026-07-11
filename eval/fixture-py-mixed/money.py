\
\
\
\
\

from decimal import Decimal


def parse_amount(input: str) -> float:
    \
    return float(input)


def to_minor_units(amount: float) -> int:
    \
    return round(amount * 100)


def from_minor_units(minor: int) -> float:
    \
    return minor / 100


def round_money(value: float) -> float:
    \
    return round(value, 2)


def to_decimal(amount: float) -> Decimal:
    \
    return Decimal(amount)
