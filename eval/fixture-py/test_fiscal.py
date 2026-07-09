"""Green-by-design tests for the fiscal fixture modules.

Every assertion uses inputs where the buggy path and a correct path produce the
same result (round numbers, single currency USD with 2 decimals, no negatives,
no DST-crossing dates), so the suite passes even though the modules ship bugs.
No test here exercises a planted bug.
"""

import sys
import pathlib
from datetime import datetime, timezone

sys.path.insert(0, str(pathlib.Path(__file__).parent))

import tax
import fx
import interest
import reports


def utc(year, month, day):
    return datetime(year, month, day, tzinfo=timezone.utc)


# ----- tax -----

def test_line_and_total_agree_on_single_line():
    # One line: per-line rounding and on-total rounding land on the same value.
    assert tax.invoice_tax_by_lines([100.0]) == 8.25
    assert tax.invoice_tax_on_total([100.0]) == 8.25


def test_extract_tax_from_gross_round_number():
    result = tax.extract_tax_from_gross(108.25)
    assert result["net"] == 100.0
    assert result["tax"] == 8.93


# ----- fx -----

def test_convert_usd_to_eur():
    assert fx.convert(100.0, "USD", "EUR") == 92.0


def test_same_currency_is_identity():
    # A same-currency "round trip" is lossless by the from == to short circuit.
    assert fx.convert(100.0, "USD", "USD") == 100.0
    assert fx.refund_in_original_currency(100.0, "USD", "USD") == 100.0


def test_settle_same_currency_keeps_total():
    invoice = {"total": 100.0, "currency": "USD"}
    settled = fx.settle_invoice(invoice, "USD")
    assert settled["total"] == 100.0
    assert settled["currency"] == "USD"


def test_total_revenue_single_currency():
    invoices = [
        {"total": 100.0, "currency": "USD"},
        {"total": 50.0, "currency": "USD"},
    ]
    assert fx.total_revenue(invoices) == 150.0


# ----- interest -----

def test_days_in_a_clean_year():
    # 2026 to 2027, no DST crossing in UTC, exactly 365 days.
    assert interest.days_between(utc(2026, 1, 1), utc(2027, 1, 1)) == 365


def test_accrued_interest_for_a_year():
    start = utc(2026, 1, 1)
    end = utc(2027, 1, 1)
    assert interest.accrued_interest(1000.0, 0.0365, start, end) == 36.5


def test_transactions_in_period_interior_dates():
    # All timestamps strictly inside the period, none on a shared boundary,
    # so inclusive-vs-exclusive does not matter here.
    txns = [
        {"at": utc(2026, 1, 10)},
        {"at": utc(2026, 1, 20)},
    ]
    picked = interest.transactions_in_period(txns, utc(2026, 1, 1), utc(2026, 2, 1))
    assert len(picked) == 2


# ----- reports -----

def test_sum_amounts_clean_floats():
    assert reports.sum_amounts([10.0, 20.0, 30.0]) == 60.0


def test_total_all_pages_stable_source():
    rows = [{"amount": 10.0}, {"amount": 20.0}, {"amount": 30.0}]

    def fetch_page(limit, offset):
        # A stable, non-mutating snapshot, so offset paging reads each row once.
        return rows[offset:offset + limit]

    assert reports.total_all_pages(fetch_page, 2) == 60.0
