\
\
\
\
\
\

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum


class DayCount(Enum):
\

    ACTUAL_365 = "actual/365"
    ACTUAL_360 = "actual/360"


@dataclass
class Transaction:
    at: datetime


def days_between(start: date, end: date) -> int:
    \
\
\
\
\
\
    return (end - start).days


def accrued_interest(
    principal: Decimal,
    annual_rate: Decimal,
    start: date,
    end: date,
    convention: DayCount,
) -> Decimal:
    \
\
\
\
\
\
    days = days_between(start, end)
    basis = Decimal(365) if convention is DayCount.ACTUAL_365 else Decimal(360)
    daily_rate = annual_rate / basis
    return (principal * daily_rate * Decimal(days)).quantize(Decimal("0.01"))


def transactions_in_period(
    txns: list[Transaction], period_start: datetime, period_end: datetime
) -> list[Transaction]:
    \
\
\
\
\
\
    return [t for t in txns if period_start <= t.at < period_end]


def monthly_statement(
    txns: list[Transaction], month_starts: list[datetime], month_index: int
) -> list[Transaction]:
    \
    return transactions_in_period(
        txns, month_starts[month_index], month_starts[month_index + 1]
    )
