"""In-memory account store (correct twin of fixture-py/store.py).

Balances are exact Decimal and every change is an atomic increment guarded by a
per-account lock, so concurrent writers cannot lose an update the way a
read-modify-write would.
"""

import threading
from dataclasses import dataclass, field
from decimal import Decimal


@dataclass
class Account:
    id: str
    currency: str
    balance: Decimal = field(default_factory=lambda: Decimal(0))


_accounts: dict[str, Account] = {}
# One lock guards the whole store; a real DB would use a row lock or an atomic
# UPDATE ... SET balance = balance + :delta. The lock here plays that role so the
# balance mutation is a single guarded critical section (IDE-3 corrected).
_lock = threading.Lock()


def get_account(account_id: str, currency: str = "USD") -> Account:
    """Fetch an account, creating a fresh zero-balance one on first sight."""
    with _lock:
        account = _accounts.get(account_id)
        if account is None:
            account = Account(id=account_id, currency=currency)
            _accounts[account_id] = account
        return account


def _apply_delta(account_id: str, delta: Decimal, currency: str) -> Account:
    """Apply a signed delta to a balance atomically under the store lock.

    Correct counterpart of IDE-3: the read and the write happen inside one locked
    section (the stand-in for a single atomic UPDATE), so two concurrent callers
    serialize and neither credit is lost.
    """
    with _lock:
        account = _accounts.get(account_id)
        if account is None:
            account = Account(id=account_id, currency=currency)
            _accounts[account_id] = account
        if account.currency != currency:
            raise ValueError(
                f"currency mismatch: account {account.currency} vs {currency}"
            )
        account.balance = account.balance + delta
        return account


def credit_account(account_id: str, amount: Decimal, currency: str = "USD") -> Account:
    """Add amount to an account balance atomically."""
    return _apply_delta(account_id, amount, currency)


def debit_account(account_id: str, amount: Decimal, currency: str = "USD") -> Account:
    """Subtract amount from an account balance atomically."""
    return _apply_delta(account_id, -amount, currency)


def reset_store() -> None:
    """Clear the store between tests."""
    with _lock:
        _accounts.clear()
