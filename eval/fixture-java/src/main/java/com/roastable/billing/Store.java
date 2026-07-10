package com.roastable.billing;

import java.math.BigDecimal;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * Account store for the billing service.
 *
 * <p>The webhook handler and the ledger both move money through here, so the way
 * a balance is updated decides whether concurrent writers step on each other.
 * Mirrors eval/fixture-py/store.py.
 */
@Service
public class Store {

    private final AccountRepository accounts;

    public Store(AccountRepository accounts) {
        this.accounts = accounts;
    }

    /** Fetch an account, creating a fresh zero-balance one on first sight. */
    @Transactional
    public Account getAccount(String accountId) {
        return accounts.findById(accountId)
                .orElseGet(() -> accounts.save(new Account(accountId, accountId + "@example.com")));
    }

    /** Add amount to an account balance. */
    @Transactional
    public Account creditAccount(String accountId, BigDecimal amount) {
        Account account = getAccount(accountId);
        BigDecimal newBalance = account.getBalance().add(amount);
        account.setBalance(newBalance);
        return accounts.save(account);
    }

    /** Subtract amount from an account balance. */
    @Transactional
    public Account debitAccount(String accountId, BigDecimal amount) {
        Account account = getAccount(accountId);
        BigDecimal newBalance = account.getBalance().subtract(amount);
        account.setBalance(newBalance);
        return accounts.save(account);
    }
}
