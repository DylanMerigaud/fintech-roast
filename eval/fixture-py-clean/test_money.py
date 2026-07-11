"""Tests for the clean money and invoice helpers.

Unlike the buggy fixture's suite, these exercise fractional cents, multiple
currencies (including JPY with 0 decimals and BHD with 3), and property-based
invariants. They pass because the code is correct, not because the inputs were
hand-picked to dodge a bug.
"""

import sys
import pathlib
from decimal import Decimal

sys.path.insert(0, str(pathlib.Path(__file__).parent))

from hypothesis import given, strategies as st

import money
import invoice
import split


# money

def test_parse_amount_is_exact_decimal():
    assert money.parse_amount("100.10") == Decimal("100.10")
    # A value with a nasty binary repr stays exact through Decimal-from-string.
    assert money.parse_amount("0.1") + money.parse_amount("0.2") == Decimal("0.3")


def test_minor_units_respect_currency_exponent():
    assert money.to_minor_units(Decimal("100.00"), "USD") == 10000
    assert money.to_minor_units(Decimal("100"), "JPY") == 100  # 0 decimals
    assert money.to_minor_units(Decimal("100.123"), "BHD") == 100123  # 3 decimals


def test_from_minor_units_round_trips():
    assert money.from_minor_units(10010, "USD") == Decimal("100.10")
    assert money.from_minor_units(100, "JPY") == Decimal("100")
    assert money.from_minor_units(100123, "BHD") == Decimal("100.123")


def test_round_money_explicit_half_up():
    # A true half at an even preceding digit: HALF_UP gives 2.67, HALF_EVEN would
    # give 2.66, so this assertion actually pins the mode (2.675 would not, it
    # rounds to 2.68 under both). This is the discriminating tie.
    assert money.round_money(Decimal("2.665")) == Decimal("2.67")


# invoice

def test_invoice_total_fractional_cents():
    lines: list[invoice.Line] = [
        {"description": "seat", "quantity": 3, "unit_price": Decimal("9.99")},
    ]
    # subtotal 29.97, minus 10% is 26.973, plus 8.25% tax is 29.198..., rounds to 29.20.
    assert invoice.invoice_total(lines, Decimal(10), Decimal("0.0825")) == Decimal(
        "29.20"
    )


# split: the invariant that makes ROU-2 correct is "parts sum to the total".

@given(
    total=st.integers(min_value=1, max_value=1_000_000).map(
        lambda cents: Decimal(cents) / 100
    ),
    weights=st.lists(
        st.integers(min_value=1, max_value=100), min_size=1, max_size=8
    ).map(lambda ws: [Decimal(w) for w in ws]),
)
def test_split_always_sums_back_to_total(total, weights):
    parts = split.split_proportionally(total, weights)
    assert sum(parts) == total
