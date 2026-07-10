package com.roastable.billing;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.math.BigDecimal;

/**
 * An account row, mapping onto the accounts table (db/schema.sql).
 *
 * <p>The webhook handler and the ledger both move money through this balance, so
 * the way it is updated (see Store) decides whether concurrent writers step on
 * each other. Mirrors the account in eval/fixture-py/store.py.
 */
@Entity
@Table(name = "accounts")
public class Account {

    @Id
    @Column(name = "id")
    private String id;

    @Column(name = "owner_email", nullable = false)
    private String ownerEmail;

    @Column(name = "balance", nullable = false, precision = 6, scale = 2)
    private BigDecimal balance = BigDecimal.ZERO;

    protected Account() {
    }

    public Account(String id, String ownerEmail) {
        this.id = id;
        this.ownerEmail = ownerEmail;
        this.balance = BigDecimal.ZERO;
    }

    public String getId() {
        return id;
    }

    public String getOwnerEmail() {
        return ownerEmail;
    }

    public BigDecimal getBalance() {
        return balance;
    }

    public void setBalance(BigDecimal balance) {
        this.balance = balance;
    }
}
