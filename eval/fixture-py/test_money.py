"""Tests for the billing money helpers.

These pass on round-number inputs (single currency, USD, whole cents), which is
exactly the trap: the suite is green while the underlying math is still wrong on
the amounts that do not land on a clean cent.
"""

import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent))

import money
import invoice
import split


# money

def test_parse_amount():
    assert money.parse_amount("100.00") == 100


def test_parse_amount_larger():
    assert money.parse_amount("250.00") == 250


def test_to_minor_units():
    assert money.to_minor_units(100) == 10000


def test_from_minor_units():
    assert money.from_minor_units(10000) == 100


def test_round_money():
    assert money.round_money(10.404) == 10.4


def test_to_decimal_round_value():
    # 5 has an exact binary representation, so this stays clean.
    assert money.to_decimal(5) == 5


# invoice

def test_line_total():
    line: invoice.Line = {"description": "seat", "quantity": 4, "unit_price": 25}
    assert invoice.line_total(line) == 100


def test_unit_price_from_bundle():
    assert invoice.unit_price_from_bundle(100, 4) == 25


def test_bundle_line_total():
    assert invoice.bundle_line_total(100, 4) == 100


def test_invoice_total_discount_then_tax():
    lines: list[invoice.Line] = [{"description": "seat", "quantity": 4, "unit_price": 25}]
    # subtotal 100, minus 10% is 90, plus 10% tax is 99.
    assert invoice.invoice_total(lines, 10, 0.10) == 99


# split

def test_split_by_weights():
    assert split.split_proportionally(100, [1, 1, 2]) == [25, 25, 50]


def test_split_equal_three_ways():
    # 90 across three equal shares lands on 30/30/30, sums back to the total.
    parts = split.split_proportionally(90, [1, 1, 1])
    assert parts == [30, 30, 30]
    assert sum(parts) == 90
