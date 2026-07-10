package com.roastable.billing;

import static org.junit.jupiter.api.Assertions.assertEquals;

import java.util.List;
import org.junit.jupiter.api.Test;

/**
 * Tests for the invoice math.
 *
 * <p>Green on round inputs (whole quantities, clean unit prices, 10 percent
 * discount and tax), so the divide-before-multiply and compounded-rounding bugs
 * stay dormant.
 */
class InvoiceTest {

    @Test
    void lineTotal() {
        assertEquals(100.0, Invoice.lineTotal(new Invoice.Line("seat", 4, 25)));
    }

    @Test
    void unitPriceFromBundle() {
        assertEquals(25.0, Invoice.unitPriceFromBundle(100, 4));
    }

    @Test
    void bundleLineTotal() {
        assertEquals(100.0, Invoice.bundleLineTotal(100, 4));
    }

    @Test
    void invoiceTotalDiscountThenTax() {
        List<Invoice.Line> lines = List.of(new Invoice.Line("seat", 4, 25));
        // subtotal 100, minus 10 percent is 90, plus 10 percent tax is 99.
        assertEquals(99.0, Invoice.invoiceTotal(lines, 10, 0.10));
    }
}
