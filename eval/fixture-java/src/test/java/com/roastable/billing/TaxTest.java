package com.roastable.billing;

import static org.junit.jupiter.api.Assertions.assertEquals;

import org.junit.jupiter.api.Test;

/**
 * Green-by-design tax tests.
 *
 * <p>Single-line invoices (per-line and on-total rounding land on the same
 * value) and a gross that divides cleanly, so the line-vs-total divergence and
 * the inclusive-vs-exclusive mixup stay dormant.
 */
class TaxTest {

    @Test
    void lineAndTotalAgreeOnSingleLine() {
        assertEquals(8.25, Tax.invoiceTaxByLines(new double[] {100.0}));
        assertEquals(8.25, Tax.invoiceTaxOnTotal(new double[] {100.0}));
    }

    @Test
    void extractTaxFromGrossRoundNumber() {
        Tax.TaxSplit result = Tax.extractTaxFromGross(108.25);
        assertEquals(100.0, result.net());
        assertEquals(8.93, result.tax());
    }
}
