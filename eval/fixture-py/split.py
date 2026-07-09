"""Split a total across parties by weight (bill splitting, cost allocation)."""

import money


def split_proportionally(total: float, weights: list[float]) -> list[float]:
    """Divide a total into weighted shares."""
    weight_sum = sum(weights)
    return [money.round_money(total * w / weight_sum) for w in weights]
