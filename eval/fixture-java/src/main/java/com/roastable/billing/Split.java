package com.roastable.billing;

/**
 * Split a total across parties by weight (bill splitting, cost allocation).
 *
 * <p>Mirrors eval/fixture-py/split.py.
 */
public final class Split {

    private Split() {
    }

    /** Divide a total into weighted shares. */
    public static double[] splitProportionally(double total, double[] weights) {
        double weightSum = 0.0;
        for (double w : weights) {
            weightSum += w;
        }
        double[] parts = new double[weights.length];
        for (int i = 0; i < weights.length; i++) {
            parts[i] = Money.roundMoney(total * weights[i] / weightSum);
        }
        return parts;
    }
}
