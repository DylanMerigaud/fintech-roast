package com.roastable.billing;

import static org.junit.jupiter.api.Assertions.assertEquals;

import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneOffset;
import java.util.List;
import org.junit.jupiter.api.Test;

/**
 * Green-by-design interest tests.
 *
 * <p>Whole-year UTC spans (no DST crossing, exactly 365 days) and interior
 * transaction dates (none on a shared boundary), so the epoch-divide day count,
 * the hardcoded 365 basis, and the inclusive-both-ends period stay dormant.
 */
class InterestTest {

    private static Instant utc(int year, int month, int day) {
        return LocalDate.of(year, month, day).atStartOfDay(ZoneOffset.UTC).toInstant();
    }

    @Test
    void daysInACleanYear() {
        // 2026 to 2027, no DST crossing in UTC, exactly 365 days.
        assertEquals(365, Interest.daysBetween(utc(2026, 1, 1), utc(2027, 1, 1)));
    }

    @Test
    void accruedInterestForAYear() {
        assertEquals(36.5, Interest.accruedInterest(1000.0, 0.0365, utc(2026, 1, 1), utc(2027, 1, 1)));
    }

    @Test
    void transactionsInPeriodInteriorDates() {
        // All timestamps strictly inside the period, none on a shared boundary,
        // so inclusive-vs-exclusive does not matter here.
        List<Interest.Txn> txns = List.of(
                new Interest.Txn(utc(2026, 1, 10)),
                new Interest.Txn(utc(2026, 1, 20)));
        List<Interest.Txn> picked = Interest.transactionsInPeriod(txns, utc(2026, 1, 1), utc(2026, 2, 1));
        assertEquals(2, picked.size());
    }
}
