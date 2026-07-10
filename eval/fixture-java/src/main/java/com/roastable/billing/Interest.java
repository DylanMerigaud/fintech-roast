package com.roastable.billing;

import java.time.Instant;
import java.util.ArrayList;
import java.util.List;

/**
 * Interest accrual and statement-period helpers for the billing service.
 *
 * <p>Self-contained: java.time only. Mirrors eval/fixture-py/interest.py.
 */
public final class Interest {

    private Interest() {
    }

    /** A transaction stamped with the instant it occurred. */
    public record Txn(Instant at) {
    }

    /** Number of whole days between two instants. */
    public static long daysBetween(Instant start, Instant end) {
        double seconds = end.getEpochSecond() - start.getEpochSecond();
        return Math.round(seconds / 86400.0);
    }

    /** Simple interest accrued on a principal between two dates. */
    public static double accruedInterest(double principal, double annualRate, Instant start, Instant end) {
        long days = daysBetween(start, end);
        double dailyRate = annualRate / 365;
        return Math.round(principal * dailyRate * days * 100) / 100.0;
    }

    /** Return the transactions whose timestamp falls inside the period. */
    public static List<Txn> transactionsInPeriod(List<Txn> txns, Instant periodStart, Instant periodEnd) {
        List<Txn> result = new ArrayList<>();
        for (Txn txn : txns) {
            if (!txn.at().isBefore(periodStart) && !txn.at().isAfter(periodEnd)) {
                result.add(txn);
            }
        }
        return result;
    }

    /** Transactions for one month, bounded by consecutive month starts. */
    public static List<Txn> monthlyStatement(List<Txn> txns, List<Instant> monthStarts, int monthIndex) {
        return transactionsInPeriod(txns, monthStarts.get(monthIndex), monthStarts.get(monthIndex + 1));
    }
}
