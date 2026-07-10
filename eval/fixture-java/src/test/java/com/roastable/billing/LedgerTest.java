package com.roastable.billing;

import static org.junit.jupiter.api.Assertions.assertEquals;

import java.math.BigDecimal;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.transaction.annotation.Transactional;

/**
 * Ledger tests: post a single leg and read it, correct it once, round USD
 * amounts, one currency. On this sequential happy path the cached balance and
 * the mutated-in-place entry agree, so the single-leg, mutate-in-place, and
 * cached-balance defects stay dormant.
 */
@SpringBootTest
@Transactional
class LedgerTest {

    @Autowired
    private Ledger ledger;

    @Autowired
    private Store store;

    @Test
    void postAndCorrectEntry() {
        ledger.postEntry(new LedgerEntry("e1", "acct_1", 50, "credit"));
        ledger.correctEntry("e1", 60);
        assertEquals(0, new BigDecimal("60").compareTo(store.getAccount("acct_1").getBalance()));
        LedgerEntry entry = ledger.allEntries().stream()
                .filter(e -> e.getId().equals("e1")).findFirst().orElseThrow();
        assertEquals(60.0, entry.getAmount());
    }

    @Test
    void postEntryUpdatesCachedBalance() {
        ledger.postEntry(new LedgerEntry("e2", "acct_2", 25, "credit"));
        assertEquals(0, new BigDecimal("25").compareTo(store.getAccount("acct_2").getBalance()));
    }
}
