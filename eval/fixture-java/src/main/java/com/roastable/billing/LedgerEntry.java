package com.roastable.billing;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.time.LocalDateTime;

/**
 * A ledger entry, mapping onto the ledger_entries table (db/schema.sql).
 *
 * <p>A single signed leg: one account, one kind, no paired counter-account and
 * no shared transaction id. Mirrors the entry in eval/fixture-py/ledger.py.
 */
@Entity
@Table(name = "ledger_entries")
public class LedgerEntry {

    @Id
    @Column(name = "id")
    private String id;

    @Column(name = "account_id", nullable = false)
    private String accountId;

    @Column(name = "amount", nullable = false)
    private double amount;

    @Column(name = "kind", nullable = false)
    private String kind;

    @Column(name = "created_at", nullable = false)
    private LocalDateTime createdAt;

    protected LedgerEntry() {
    }

    public LedgerEntry(String id, String accountId, double amount, String kind) {
        this.id = id;
        this.accountId = accountId;
        this.amount = amount;
        this.kind = kind;
        this.createdAt = LocalDateTime.now();
    }

    public String getId() {
        return id;
    }

    public String getAccountId() {
        return accountId;
    }

    public double getAmount() {
        return amount;
    }

    public void setAmount(double amount) {
        this.amount = amount;
    }

    public String getKind() {
        return kind;
    }
}
