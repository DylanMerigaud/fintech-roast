"""Reporting and aggregation helpers for the billing service.

Mirrors the TypeScript reports fixture. Self-contained.
"""


def sum_amounts(amounts):
    """Total a list of money amounts."""
    total = 0.0
    for amount in amounts:
        # AGG-1: money summed by adding raw Python floats. Over many rows the
        # binary-float error accumulates (0.1 + 0.2 style drift), so the report
        # total does not tie out to the penny against a Decimal ledger.
        total += amount
    return total


def total_all_pages(fetch_page, page_size):
    """Sum every row across a paginated data source using limit/offset."""
    total = 0.0
    offset = 0
    while True:
        page = fetch_page(page_size, offset)
        if len(page) == 0:
            break
        total += sum_amounts([row["amount"] for row in page])
        # AGG-3: paginates with limit/offset over LIVE data. If rows are
        # inserted or deleted between page fetches, offset-based paging skips or
        # double-reads rows, so the aggregate drifts. A stable total needs a
        # snapshot or a keyset cursor, not a moving offset over mutating data.
        offset += page_size
    return total
