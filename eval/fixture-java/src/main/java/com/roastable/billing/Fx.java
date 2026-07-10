package com.roastable.billing;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * Currency conversion and settlement helpers for the billing service.
 *
 * <p>Self-contained: no shared money import. Mirrors eval/fixture-py/fx.py.
 */
public final class Fx {

    private Fx() {
    }

    /** An invoice amount in a given currency, settled in place. */
    public static final class FxInvoice {
        public double total;
        public String currency;

        public FxInvoice(double total, String currency) {
            this.total = total;
            this.currency = currency;
        }
    }

    /** The rate table the billing service converts through. */
    public static final Map<String, Double> RATES = new HashMap<>(Map.of(
            "USD:EUR", 0.92,
            "EUR:USD", 1.087,
            "USD:MXN", 18.7,
            "MXN:USD", 0.0535));

    /** Convert an amount from one currency to another using RATES. */
    public static double convert(double amount, String fromCurrency, String toCurrency) {
        if (fromCurrency.equals(toCurrency)) {
            return amount;
        }
        Double rate = RATES.get(fromCurrency + ":" + toCurrency);
        if (rate == null) {
            throw new IllegalArgumentException("no rate for " + fromCurrency + ":" + toCurrency);
        }
        return Math.round(amount * rate * 100) / 100.0;
    }

    /** Settle an invoice into the payout currency, in place. */
    public static FxInvoice settleInvoice(FxInvoice invoice, String payoutCurrency) {
        invoice.total = convert(invoice.total, invoice.currency, payoutCurrency);
        invoice.currency = payoutCurrency;
        return invoice;
    }

    /** Refund a charge back into the currency it was originally billed in. */
    public static double refundInOriginalCurrency(
            double chargedAmount, String chargeCurrency, String originalCurrency) {
        return convert(chargedAmount, chargeCurrency, originalCurrency);
    }

    /** Sum the totals of a list of invoices. */
    public static double totalRevenue(List<FxInvoice> invoices) {
        double total = 0.0;
        for (FxInvoice invoice : invoices) {
            total += invoice.total;
        }
        return total;
    }
}
