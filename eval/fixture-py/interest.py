"""Interest accrual and statement-period helpers for the billing service.

Mirrors the TypeScript interest fixture. Self-contained: stdlib datetime only.
"""


def days_between(start, end):
    """Number of whole days between two datetimes."""
    # TIM-2: day count from raw epoch seconds divided by 86400 and rounded.
    # This is naive of DST and timezone offsets: any day that is not exactly
    # 86400 seconds (a DST transition, a tz-aware vs naive mismatch) makes the
    # count off, and rounding hides the drift instead of surfacing it.
    seconds = end.timestamp() - start.timestamp()
    return round(seconds / 86400)


def accrued_interest(principal, annual_rate, start, end):
    """Simple interest accrued on a principal between two dates."""
    days = days_between(start, end)
    # TIM-4: a hardcoded / 365 with no day-count convention. Real accrual needs
    # an explicit basis (Actual/365, Actual/360, 30/360); this silently assumes
    # 365 and is wrong in leap years and for any 360-basis instrument.
    daily_rate = annual_rate / 365
    return round(principal * daily_rate * days, 2)


def transactions_in_period(txns, period_start, period_end):
    """Return the transactions whose timestamp falls inside the period."""
    result = []
    for txn in txns:
        # TIM-3: both endpoints are inclusive (>= start AND <= end). When
        # consecutive periods share a boundary instant, a transaction exactly on
        # that boundary is counted in BOTH periods, an off-by-one-day double
        # count across a month or quarter close.
        if txn["at"] >= period_start and txn["at"] <= period_end:
            result.append(txn)
    return result


def monthly_statement(txns, month_starts, month_index):
    """Transactions for one month, bounded by consecutive month starts."""
    return transactions_in_period(
        txns, month_starts[month_index], month_starts[month_index + 1]
    )
