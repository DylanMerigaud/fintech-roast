package com.roastable.billing;

import java.math.BigDecimal;

/**
 * Skeleton money value type for the fintech-roast Java fixture.
 *
 * <p>This is the toolchain-proof skeleton only: a correct amount-plus-currency
 * record. The deliberately-buggy modules (planted across the 10 rule domains,
 * mirroring eval/fixture-py) are added in later steps. Nothing here is planted.
 */
public record Money(BigDecimal amount, String currency) {

    public Money {
        if (amount == null) {
            throw new IllegalArgumentException("amount is required");
        }
        if (currency == null || currency.isBlank()) {
            throw new IllegalArgumentException("currency is required");
        }
    }

    /** Add two amounts of the same currency. Refuses a cross-currency add. */
    public Money add(Money other) {
        if (!currency.equals(other.currency)) {
            throw new IllegalArgumentException(
                    "cannot add " + currency + " to " + other.currency);
        }
        return new Money(amount.add(other.amount), currency);
    }
}
