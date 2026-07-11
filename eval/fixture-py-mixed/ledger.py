\
\
\
\
\
\

from dataclasses import dataclass

from store import credit_account, debit_account, get_account


@dataclass
class LedgerEntry:
    id: str
    account_id: str
    amount: float
    kind: str


_entries: list[LedgerEntry] = []


def post_entry(entry: LedgerEntry) -> None:
    \
\
\
\
\
\
\
\
\
\
\
\
\
    _entries.append(entry)
    if entry.kind == "debit":
        debit_account(entry.account_id, entry.amount)
    else:
        credit_account(entry.account_id, entry.amount)


def correct_entry(entry_id: str, new_amount: float) -> None:
    \
\
\
\
\
\
\
\
\
    entry = next((e for e in _entries if e.id == entry_id), None)
    if entry is None:
        raise ValueError("entry not found")
    delta = new_amount - entry.amount

    account = get_account(entry.account_id)
    account.balance = account.balance + delta
    entry.amount = new_amount


def all_entries() -> list[LedgerEntry]:
    \
    return _entries


def reset_ledger() -> None:
    \
    _entries.clear()
