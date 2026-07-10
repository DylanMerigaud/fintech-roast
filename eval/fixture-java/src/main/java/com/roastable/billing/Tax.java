package com.roastable.billing;

/**
 * Sales tax helpers for the billing service.
 *
 * <p>Self-contained on purpose: it does not use the shared money helper, it
 * keeps a small local rounder instead. Mirrors eval/fixture-py/tax.py.
 */
public final class Tax {

    private Tax() {
    }

    /** The sales tax rate applied across the billing service. */
    public static final double SALES_TAX_RATE = 0.0825;

    /** A tax-inclusive gross price split into its net and tax parts. */
    public record TaxSplit(double net, double tax) {
    }

    /** Round to two decimals the naive way. */
    static double roundMoney(double amount) {
        return Math.round((amount + 0.0) * 100) / 100.0;
    }

    /** Tax computed per line, each line rounded, then the sum rounded again. */
    public static double invoiceTaxByLines(double[] lineAmounts) {
        double tax = 0.0;
        for (double amount : lineAmounts) {
            tax += roundMoney(amount * SALES_TAX_RATE);
        }
        return roundMoney(tax);
    }

    /** Tax computed once on the invoice total, rounded once. */
    public static double invoiceTaxOnTotal(double[] lineAmounts) {
        double total = 0.0;
        for (double amount : lineAmounts) {
            total += amount;
        }
        return roundMoney(total * SALES_TAX_RATE);
    }

    /** Split a tax-inclusive gross price into net and tax. */
    public static TaxSplit extractTaxFromGross(double gross) {
        double net = roundMoney(gross / (1 + SALES_TAX_RATE));
        double tax = roundMoney(gross * SALES_TAX_RATE);
        return new TaxSplit(net, tax);
    }
}
