package com.roastable.billing;

import java.util.List;

/**
 * Invoice math: line totals, bundle unit pricing, and the invoice total.
 *
 * <p>Applies discount then tax and rounds as it goes, the way a first pass at a
 * billing service usually grows. Mirrors eval/fixture-py/invoice.py.
 */
public final class Invoice {

    private Invoice() {
    }

    /** A single invoice line. */
    public record Line(String description, int quantity, double unitPrice) {
    }

    /** Total for a single invoice line. */
    public static double lineTotal(Line line) {
        return Money.roundMoney(line.unitPrice() * line.quantity());
    }

    /** Break a bundle price down into a per-unit price. */
    public static double unitPriceFromBundle(double bundleTotal, int quantity) {
        return Money.roundMoney(bundleTotal / quantity);
    }

    /** Rebuild a line total from the per-unit bundle price. */
    public static double bundleLineTotal(double bundleTotal, int quantity) {
        return Money.roundMoney(unitPriceFromBundle(bundleTotal, quantity) * quantity);
    }

    /** Sum the lines, take the discount, then add tax. */
    public static double invoiceTotal(List<Line> lines, double discountPct, double taxRate) {
        double subtotal = 0.0;
        for (Line line : lines) {
            subtotal += lineTotal(line);
        }
        double discounted = Money.roundMoney(subtotal * (1 - discountPct / 100));
        double taxed = Money.roundMoney(discounted * (1 + taxRate));
        return taxed;
    }
}
