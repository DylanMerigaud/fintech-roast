"""Interest accrual and statement periods (correct twin of fixture-py/interest.py).

Day counts come from calendar dates (not raw epoch-seconds / 86400), the accrual
takes an explicit day-count convention, and statement periods are half-open so a
boundary transaction lands in exactly one period.
"""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum


class DayCount(Enum):
    """Explicit day-count conventions, so a caller must choose the basis."""

    ACTUAL_365 = "actual/365"
    ACTUAL_360 = "actual/360"


@dataclass
class Transaction:
    at: datetime


def days_between(start: date, end: date) -> int:
    """Whole calendar days between two dates.

    Correct counterpart of TIM-2: the count comes from date arithmetic on
    calendar dates, so a DST transition (a day that is not 86400 seconds long)
    cannot skew it. Working in dates sidesteps wall-clock offsets entirely.
    """
    return (end - start).days


def accrued_interest(
    principal: Decimal,
    annual_rate: Decimal,
    start: date,
    end: date,
    convention: DayCount,
) -> Decimal:
    """Simple interest between two dates under an explicit day-count convention.

    Correct counterpart of TIM-4: the basis (365 or 360) is a required argument,
    not a silent hardcoded / 365, so the caller states the instrument's
    convention and leap years / 360-basis instruments are handled correctly.
    """
    days = days_between(start, end)
    basis = Decimal(365) if convention is DayCount.ACTUAL_365 else Decimal(360)
    daily_rate = annual_rate / basis
    return (principal * daily_rate * Decimal(days)).quantize(Decimal("0.01"))


def transactions_in_period(
    txns: list[Transaction], period_start: datetime, period_end: datetime
) -> list[Transaction]:
    """Transactions in a half-open period [start, end).

    Correct counterpart of TIM-3: the period is half-open (start inclusive, end
    exclusive), so a transaction exactly on a shared boundary belongs to exactly
    one of two consecutive periods, never both.
    """
    return [t for t in txns if period_start <= t.at < period_end]


def monthly_statement(
    txns: list[Transaction], month_starts: list[datetime], month_index: int
) -> list[Transaction]:
    """Transactions for one month, bounded by consecutive month starts."""
    return transactions_in_period(
        txns, month_starts[month_index], month_starts[month_index + 1]
    )
