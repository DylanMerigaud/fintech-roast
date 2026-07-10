package com.roastable.billing;

import java.math.BigDecimal;
import java.util.List;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * Ledger for the billing service.
 *
 * <p>Records money movements and keeps each account balance in step through the
 * store: a flat list of entries, a post that also bumps the cached balance, and
 * a correction path. Mirrors eval/fixture-py/ledger.py.
 */
@Service
public class Ledger {

    private final LedgerEntryRepository entries;
    private final Store store;

    public Ledger(LedgerEntryRepository entries, Store store) {
        this.entries = entries;
        this.store = store;
    }

    /** Post a movement to the ledger and update the cached balance. */
    @Transactional
    public void postEntry(LedgerEntry entry) {
        if ("debit".equals(entry.getKind())) {
            store.debitAccount(entry.getAccountId(), BigDecimal.valueOf(entry.getAmount()));
        } else {
            store.creditAccount(entry.getAccountId(), BigDecimal.valueOf(entry.getAmount()));
        }
        entries.save(entry);
    }

    /** Correct an already-posted entry to a new amount. */
    @Transactional
    public void correctEntry(String entryId, double newAmount) {
        LedgerEntry entry = entries.findById(entryId)
                .orElseThrow(() -> new IllegalArgumentException("entry not found"));
        double delta = newAmount - entry.getAmount();
        store.creditAccount(entry.getAccountId(), BigDecimal.valueOf(delta));
        entry.setAmount(newAmount);
        entries.save(entry);
    }

    /** Return every ledger entry. */
    @Transactional
    public List<LedgerEntry> allEntries() {
        return entries.findAll();
    }
}
