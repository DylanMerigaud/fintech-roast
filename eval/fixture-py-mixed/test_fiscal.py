\
\
\
\
\
\
\

import sys
import pathlib
from datetime import date, datetime, timezone
from decimal import Decimal

sys.path.insert(0, str(pathlib.Path(__file__).parent))

import tax
import fx
import interest
import reports


def utc(year, month, day, hour=0):
    return datetime(year, month, day, hour, tzinfo=timezone.utc)


def test_tax_paths_agree_on_multi_line_invoice():
    lines = [Decimal("33.33"), Decimal("66.67"), Decimal("10.01")]
    on_total = tax.invoice_tax(sum(lines, Decimal(0)))
    from_lines = tax.invoice_tax_from_lines(lines)
    assert on_total == from_lines


def test_extract_tax_reconstructs_gross():
    result = tax.extract_tax_from_gross(Decimal("108.25"))
    assert result["net"] + result["tax"] == Decimal("108.25")


def test_convert_tags_the_rate():
    result = fx.convert(Decimal("100.00"), "USD", "EUR")
    assert result.amount == Decimal("92.00")
    assert result.currency == "EUR"
    assert result.rate.source == "ecb"


def test_convert_back_uses_reciprocal_rate():

    reverse = fx.get_rate("EUR", "USD")
    assert reverse.value == Decimal(1) / Decimal("0.92")


def test_settle_keeps_the_original_billed_amount():
    settled = fx.settle_invoice({"total": Decimal("100.00"), "currency": "USD"}, "EUR")
    assert settled["billed_total"] == Decimal("100.00")
    assert settled["billed_currency"] == "USD"
    assert settled["settled_currency"] == "EUR"


def test_total_revenue_across_currencies():
    invoices = [
        {"total": Decimal("100.00"), "currency": "USD"},
        {"total": Decimal("92.00"), "currency": "EUR"},
    ]
    result = fx.total_revenue(invoices, "USD")

    assert result.amount == Decimal("200.00")
    assert result.currency == "USD"


def test_days_across_a_dst_boundary():


    assert interest.days_between(date(2026, 3, 1), date(2026, 4, 1)) == 31


def test_accrued_interest_requires_a_convention():
    start = date(2026, 1, 1)
    end = date(2027, 1, 1)
    got = interest.accrued_interest(
        Decimal("1000"), Decimal("0.0365"), start, end, interest.DayCount.ACTUAL_365
    )
    assert got == Decimal("36.50")


def test_boundary_transaction_lands_in_one_period():
    boundary = utc(2026, 2, 1)
    txns = [interest.Transaction(at=boundary)]
    jan = interest.transactions_in_period(txns, utc(2026, 1, 1), boundary)
    feb = interest.transactions_in_period(txns, boundary, utc(2026, 3, 1))

    assert len(jan) == 0
    assert len(feb) == 1


def test_sum_amounts_no_float_drift():
    amounts = [Decimal("0.1"), Decimal("0.2")]
    assert reports.sum_amounts(amounts) == Decimal("0.3")


def test_total_by_keyset_stable_under_ordering():
    rows = [
        {"id": "a", "amount": Decimal("10.00")},
        {"id": "b", "amount": Decimal("20.00")},
        {"id": "c", "amount": Decimal("30.01")},
    ]

    def fetch_after(cursor, limit):
        start = 0 if cursor is None else next(
            i + 1 for i, r in enumerate(rows) if r["id"] == cursor
        )
        return rows[start : start + limit]

    assert reports.total_by_keyset(fetch_after, 2) == Decimal("60.01")
