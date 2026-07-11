\
\
\
\
\

from decimal import Decimal


def sum_amounts(amounts: list[Decimal]) -> Decimal:
    \
\
\
\
\
\
    total = Decimal(0)
    for amount in amounts:
        total += amount
    return total


def total_by_keyset(fetch_after, page_size: int) -> Decimal:
    \
\
\
\
\
\
\
    total = Decimal(0)
    cursor: str | None = None
    while True:
        page = fetch_after(cursor, page_size)
        if not page:
            break
        total += sum_amounts([row["amount"] for row in page])
        cursor = page[-1]["id"]
    return total
