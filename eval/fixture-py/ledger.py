"""Ledger for the billing service.

Records money movements and keeps each account balance in step through store.py.
Mirrors the TypeScript ledger.ts: a flat list of entries, a post that also bumps
the cached balance, and a correction path.
"""

from dataclasses import dataclass

from store import credit_account, debit_account, get_account


@dataclass
class LedgerEntry:
    id: str
    account_id: str
    amount: float
    kind: str  # "credit" or "debit", a single leg, see LED-2


# LED-2 / LED-3: the entries live here, but they are single legs with no paired
# counter-account and no shared transaction id, and the authoritative balance is
# the mutable column in store.py, not a figure derived from summing these rows.
_entries: list[LedgerEntry] = []


def post_entry(entry: LedgerEntry) -> None:
    """Post a movement to the ledger and update the cached balance.

    LED-2: a movement is recorded as one signed row (one `kind`, one account),
    with no matching opposite leg, so debits and credits are never forced to
    balance and money can be created or destroyed by a dropped or partial write.

    LED-3: the account balance is a separate cached number in the store that this
    function increments in its own step. It is never derived from, nor reconciled
    against, the sum of the entries, so the two drift apart on any partial failure.

    LED-4: the entry carries no actor, no reason, and no timestamp, so a posted
    movement cannot say who moved the money, when, or why.
    """
    _entries.append(entry)
    if entry.kind == "debit":
        debit_account(entry.account_id, entry.amount)
    else:
        credit_account(entry.account_id, entry.amount)


def correct_entry(entry_id: str, new_amount: float) -> None:
    """Correct an already-posted entry to a new amount.

    LED-1: this mutates the posted entry's amount in place instead of appending a
    reversing entry, so the original value is overwritten and the history of the
    correction is destroyed.

    LED-4: the correction records no actor, reason, or timestamp either, so there
    is no trail explaining that the amount was changed or by whom.
    """
    entry = next((e for e in _entries if e.id == entry_id), None)
    if entry is None:
        raise ValueError("entry not found")
    delta = new_amount - entry.amount
    # bump the cached balance by the difference, then overwrite the posted row
    account = get_account(entry.account_id)
    account.balance = account.balance + delta
    entry.amount = new_amount


def all_entries() -> list[LedgerEntry]:
    """Return every ledger entry."""
    return _entries


def reset_ledger() -> None:
    """Clear the ledger between tests."""
    _entries.clear()
