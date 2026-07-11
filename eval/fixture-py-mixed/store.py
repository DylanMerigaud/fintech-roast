"""In-memory account store for the billing service.

Stands in for the accounts table (db/schema.sql). The webhook handler and the
ledger both move money through here, so the way a balance is updated decides
whether concurrent writers step on each other.
"""

from dataclasses import dataclass


@dataclass
class Account:
    id: str
    balance: float = 0.0


_accounts: dict[str, Account] = {}


def get_account(account_id: str) -> Account:
    """Fetch an account, creating a fresh zero-balance one on first sight."""
    account = _accounts.get(account_id)
    if account is None:
        account = Account(id=account_id, balance=0.0)
        _accounts[account_id] = account
    return account


def save_account(account: Account) -> None:
    """Persist an account back into the store."""
    _accounts[account.id] = account


def credit_account(account_id: str, amount: float) -> Account:
    """Add amount to an account balance.

    IDE-3: this is a read-modify-write. It reads the current balance, adds in
    Python, then writes the whole computed value back, with no row lock and no
    atomic increment. Two callers that read the same starting balance both write
    their own total, so one credit is lost (the classic lost update).
    """
    account = get_account(account_id)
    new_balance = account.balance + amount
    account.balance = new_balance
    save_account(account)
    return account


def debit_account(account_id: str, amount: float) -> Account:
    """Subtract amount from an account balance.

    IDE-3: same read-modify-write pattern as credit_account, and the funds check
    (if any) would live in Python between the read and the write rather than in a
    single guarded UPDATE, so concurrent debits can overdraw the account.
    """
    account = get_account(account_id)
    new_balance = account.balance - amount
    account.balance = new_balance
    save_account(account)
    return account


def reset_store() -> None:
    """Clear the store between tests."""
    _accounts.clear()
