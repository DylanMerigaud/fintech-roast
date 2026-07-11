\
\
\
\
\
\

from dataclasses import dataclass


@dataclass
class Account:
    id: str
    balance: float = 0.0


_accounts: dict[str, Account] = {}


def get_account(account_id: str) -> Account:
    \
    account = _accounts.get(account_id)
    if account is None:
        account = Account(id=account_id, balance=0.0)
        _accounts[account_id] = account
    return account


def save_account(account: Account) -> None:
    \
    _accounts[account.id] = account


def credit_account(account_id: str, amount: float) -> Account:
    \
\
\
\
\
\
\
    account = get_account(account_id)
    new_balance = account.balance + amount
    account.balance = new_balance
    save_account(account)
    return account


def debit_account(account_id: str, amount: float) -> Account:
    \
\
\
\
\
\
    account = get_account(account_id)
    new_balance = account.balance - amount
    account.balance = new_balance
    save_account(account)
    return account


def reset_store() -> None:
    \
    _accounts.clear()
