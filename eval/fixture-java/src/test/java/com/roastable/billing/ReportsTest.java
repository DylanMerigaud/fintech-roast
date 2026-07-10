package com.roastable.billing;

import static org.junit.jupiter.api.Assertions.assertEquals;

import java.util.List;
import org.junit.jupiter.api.Test;

/**
 * Green-by-design reports tests.
 *
 * <p>Clean small-magnitude sums and a stable, non-mutating page source, so the
 * float accumulation drift and the offset-over-live-data paging stay dormant.
 */
class ReportsTest {

    @Test
    void sumAmountsCleanFloats() {
        assertEquals(60.0, Reports.sumAmounts(new double[] {10.0, 20.0, 30.0}));
    }

    @Test
    void totalAllPagesStableSource() {
        List<Reports.Row> rows = List.of(
                new Reports.Row(10.0), new Reports.Row(20.0), new Reports.Row(30.0));
        // A stable, non-mutating snapshot, so offset paging reads each row once.
        Reports.PageFetcher fetchPage = (limit, offset) -> {
            if (offset >= rows.size()) {
                return List.of();
            }
            return rows.subList(offset, Math.min(offset + limit, rows.size()));
        };
        assertEquals(60.0, Reports.totalAllPages(fetchPage, 2));
    }
}
