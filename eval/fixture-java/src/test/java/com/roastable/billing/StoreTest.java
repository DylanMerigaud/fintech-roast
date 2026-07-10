package com.roastable.billing;

import static org.junit.jupiter.api.Assertions.assertEquals;

import java.math.BigDecimal;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.transaction.annotation.Transactional;

/**
 * Store tests: one sequential balance update at a time, never concurrent, so the
 * read-modify-write has nothing to race against and looks correct here. Round USD
 * amounts. Boots the Spring context and the H2 schema.
 */
@SpringBootTest
@Transactional
class StoreTest {

    @Autowired
    private Store store;

    @Test
    void creditAccountSetsBalance() {
        Account account = store.creditAccount("acct_1", new BigDecimal("100"));
        assertEquals(0, new BigDecimal("100").compareTo(account.getBalance()));
    }

    @Test
    void debitAfterCreditIsSequential() {
        store.creditAccount("acct_1", new BigDecimal("100"));
        Account account = store.debitAccount("acct_1", new BigDecimal("40"));
        assertEquals(0, new BigDecimal("60").compareTo(account.getBalance()));
    }
}
