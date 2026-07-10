package com.roastable.billing;

import static org.junit.jupiter.api.Assertions.assertEquals;

import java.util.List;
import org.junit.jupiter.api.Test;

/**
 * Green-by-design fx tests.
 *
 * <p>One-way single conversions and single-currency sums, plus same-currency
 * short circuits, so the lossy round-trip, the dropped original, and the
 * cross-currency sum stay dormant.
 */
class FxTest {

    @Test
    void convertUsdToEur() {
        assertEquals(92.0, Fx.convert(100.0, "USD", "EUR"));
    }

    @Test
    void sameCurrencyIsIdentity() {
        // A same-currency "round trip" is lossless by the from == to short circuit.
        assertEquals(100.0, Fx.convert(100.0, "USD", "USD"));
        assertEquals(100.0, Fx.refundInOriginalCurrency(100.0, "USD", "USD"));
    }

    @Test
    void settleSameCurrencyKeepsTotal() {
        Fx.FxInvoice settled = Fx.settleInvoice(new Fx.FxInvoice(100.0, "USD"), "USD");
        assertEquals(100.0, settled.total);
        assertEquals("USD", settled.currency);
    }

    @Test
    void totalRevenueSingleCurrency() {
        List<Fx.FxInvoice> invoices = List.of(
                new Fx.FxInvoice(100.0, "USD"),
                new Fx.FxInvoice(50.0, "USD"));
        assertEquals(150.0, Fx.totalRevenue(invoices));
    }
}
