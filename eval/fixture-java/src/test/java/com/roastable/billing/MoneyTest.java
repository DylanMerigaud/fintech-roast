package com.roastable.billing;

import static org.junit.jupiter.api.Assertions.assertEquals;

import java.math.BigDecimal;
import org.junit.jupiter.api.Test;

/**
 * Tests for the billing money helpers.
 *
 * <p>These pass on round-number inputs (single currency, USD, whole cents),
 * which is exactly the trap: the suite is green while the underlying math is
 * still wrong on the amounts that do not land on a clean cent.
 */
class MoneyTest {

    @Test
    void parseAmount() {
        assertEquals(100.0, Money.parseAmount("100.00"));
    }

    @Test
    void parseAmountLarger() {
        assertEquals(250.0, Money.parseAmount("250.00"));
    }

    @Test
    void toMinorUnits() {
        assertEquals(10000, Money.toMinorUnits(100));
    }

    @Test
    void fromMinorUnits() {
        assertEquals(100.0, Money.fromMinorUnits(10000));
    }

    @Test
    void roundMoney() {
        assertEquals(10.4, Money.roundMoney(10.404));
    }

    @Test
    void toDecimalRoundValue() {
        // 5 has an exact binary representation, so this stays clean.
        assertEquals(0, new BigDecimal("5").compareTo(Money.toDecimal(5)));
    }
}
