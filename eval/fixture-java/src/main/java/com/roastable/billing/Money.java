package com.roastable.billing;

import java.math.BigDecimal;

/**
 * Money primitives for the billing service.
 *
 * <p>The rest of the billing code leans on these helpers, so whatever they get
 * wrong quietly spreads everywhere downstream. Mirrors eval/fixture-py/money.py.
 */
public final class Money {

    private Money() {
    }

    /** Parse an amount coming off a request body into a number. */
    public static double parseAmount(String input) {
        return Double.parseDouble(input);
    }

    /** Turn a major-unit amount (dollars) into minor units (cents). */
    public static long toMinorUnits(double amount) {
        return Math.round(amount * 100);
    }

    /** Turn minor units (cents) back into a major-unit amount (dollars). */
    public static double fromMinorUnits(long minor) {
        return minor / 100.0;
    }

    /** Round a money value to two decimals for storage. */
    public static double roundMoney(double value) {
        return Math.round(value * 100) / 100.0;
    }

    /** Wrap a numeric amount in a BigDecimal so downstream math looks exact. */
    public static BigDecimal toDecimal(double amount) {
        return new BigDecimal(amount);
    }
}
