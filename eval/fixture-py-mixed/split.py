\

from decimal import Decimal

import money


def split_proportionally(total: Decimal, weights: list[Decimal]) -> list[Decimal]:
    \
\
\
\
\
\
\
    weight_sum = sum(weights)
    if weight_sum == 0:
        raise ValueError("weights must not sum to zero")

    minor_total = money.to_minor_units(total, "USD")
    exact_shares = [Decimal(minor_total) * w / weight_sum for w in weights]

    floored = [int(share) for share in exact_shares]
    residual = minor_total - sum(floored)


    remainders = sorted(
        range(len(weights)),
        key=lambda i: exact_shares[i] - floored[i],
        reverse=True,
    )
    for i in remainders[:residual]:
        floored[i] += 1

    return [money.from_minor_units(minor, "USD") for minor in floored]
