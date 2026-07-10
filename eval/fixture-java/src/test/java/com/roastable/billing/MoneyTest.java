package com.roastable.billing;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import java.math.BigDecimal;
import org.junit.jupiter.api.Test;

/**
 * Skeleton test: proves the Maven + JUnit 5 toolchain compiles and runs green.
 * Round-number, single-currency happy path (the green-by-design convention the
 * planted-bug modules will rely on later).
 */
class MoneyTest {

    @Test
    void addsSameCurrency() {
        Money a = new Money(new BigDecimal("10.00"), "USD");
        Money b = new Money(new BigDecimal("5.00"), "USD");
        assertEquals(new BigDecimal("15.00"), a.add(b).amount());
    }

    @Test
    void refusesCrossCurrencyAdd() {
        Money usd = new Money(new BigDecimal("10.00"), "USD");
        Money eur = new Money(new BigDecimal("10.00"), "EUR");
        assertThrows(IllegalArgumentException.class, () -> usd.add(eur));
    }
}
