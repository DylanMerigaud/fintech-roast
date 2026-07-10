package com.roastable.billing;

import org.springframework.data.jpa.repository.JpaRepository;

/** Spring Data access to the ledger_entries table. */
public interface LedgerEntryRepository extends JpaRepository<LedgerEntry, String> {
}
