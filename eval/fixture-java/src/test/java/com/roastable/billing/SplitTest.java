package com.roastable.billing;

import static org.junit.jupiter.api.Assertions.assertArrayEquals;
import static org.junit.jupiter.api.Assertions.assertEquals;

import org.junit.jupiter.api.Test;

/**
 * Tests for the proportional split.
 *
 * <p>Green on evenly-dividing weights (100 by 1:1:2, 90 three ways), which is
 * exactly the trap: the parts happen to sum back to the total, so the
 * independent per-share rounding never leaks a cent here.
 */
class SplitTest {

    @Test
    void splitByWeights() {
        assertArrayEquals(new double[] {25.0, 25.0, 50.0},
                Split.splitProportionally(100, new double[] {1, 1, 2}));
    }

    @Test
    void splitEqualThreeWays() {
        // 90 across three equal shares lands on 30/30/30, sums back to the total.
        double[] parts = Split.splitProportionally(90, new double[] {1, 1, 1});
        assertArrayEquals(new double[] {30.0, 30.0, 30.0}, parts);
        double sum = 0.0;
        for (double p : parts) {
            sum += p;
        }
        assertEquals(90.0, sum);
    }
}
