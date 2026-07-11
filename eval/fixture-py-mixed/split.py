"""Split a total across parties by weight (correct twin of fixture-py/split.py)."""

from decimal import Decimal

import money


def split_proportionally(total: Decimal, weights: list[Decimal]) -> list[Decimal]:
    """Divide a total into weighted shares that sum back to the total.

    Correct counterpart of ROU-2: each share is rounded down to the currency
    scale, then the residual (total minus the sum of the rounded shares) is
    handed out one minor unit at a time (largest-remainder). The returned parts
    always sum EXACTLY to the input total, with no penny created or lost.
    """
    weight_sum = sum(weights)
    if weight_sum == 0:
        raise ValueError("weights must not sum to zero")

    minor_total = money.to_minor_units(total, "USD")
    exact_shares = [Decimal(minor_total) * w / weight_sum for w in weights]

    floored = [int(share) for share in exact_shares]
    residual = minor_total - sum(floored)

    # Hand the leftover minor units to the shares with the largest fractional part.
    remainders = sorted(
        range(len(weights)),
        key=lambda i: exact_shares[i] - floored[i],
        reverse=True,
    )
    for i in remainders[:residual]:
        floored[i] += 1

    return [money.from_minor_units(minor, "USD") for minor in floored]
