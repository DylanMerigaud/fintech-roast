package com.roastable.billing;

import java.util.List;

/**
 * Reporting and aggregation helpers for the billing service.
 *
 * <p>Self-contained. Mirrors eval/fixture-py/reports.py.
 */
public final class Reports {

    private Reports() {
    }

    /** A reporting row carrying a money amount. */
    public record Row(double amount) {
    }

    /** A paginated data source: return up to {@code limit} rows from {@code offset}. */
    @FunctionalInterface
    public interface PageFetcher {
        List<Row> fetch(int limit, int offset);
    }

    /** Total a list of money amounts. */
    public static double sumAmounts(double[] amounts) {
        double total = 0.0;
        for (double amount : amounts) {
            total += amount;
        }
        return total;
    }

    /** Sum every row across a paginated data source using limit/offset. */
    public static double totalAllPages(PageFetcher fetchPage, int pageSize) {
        double total = 0.0;
        int offset = 0;
        while (true) {
            List<Row> page = fetchPage.fetch(pageSize, offset);
            if (page.isEmpty()) {
                break;
            }
            double[] amounts = new double[page.size()];
            for (int i = 0; i < page.size(); i++) {
                amounts[i] = page.get(i).amount();
            }
            total += sumAmounts(amounts);
            offset += pageSize;
        }
        return total;
    }
}
