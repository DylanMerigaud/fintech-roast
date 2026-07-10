"""Reporting and aggregation (correct twin of fixture-py/reports.py).

Money is summed as Decimal, and paginated aggregation runs against a stable
keyset cursor snapshot rather than a moving limit/offset over live data.
"""

from decimal import Decimal


def sum_amounts(amounts: list[Decimal]) -> Decimal:
    """Total a list of money amounts exactly.

    Correct counterpart of AGG-1: the running total is a Decimal, so there is no
    accumulating binary-float error and the report ties out to the penny against
    a Decimal ledger.
    """
    total = Decimal(0)
    for amount in amounts:
        total += amount
    return total


def total_by_keyset(fetch_after, page_size: int) -> Decimal:
    """Sum every row across a paginated source using a stable keyset cursor.

    Correct counterpart of AGG-3: paging advances by the last row's id (a keyset
    cursor), not a numeric offset, so rows inserted or deleted between fetches do
    not shift the window and cannot be skipped or double-counted. fetch_after
    returns rows with id greater than the cursor, ordered by id.
    """
    total = Decimal(0)
    cursor: str | None = None
    while True:
        page = fetch_after(cursor, page_size)
        if not page:
            break
        total += sum_amounts([row["amount"] for row in page])
        cursor = page[-1]["id"]
    return total
