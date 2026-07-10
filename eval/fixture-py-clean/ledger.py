"""Ledger (correct twin of fixture-py/ledger.py).

Double-entry (every movement posts a balanced pair of legs under one transaction
id), corrections append a reversing transaction instead of mutating history, the
balance is DERIVED by summing the entries, and every entry carries actor, reason,
and timestamp for a full audit trail.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal


@dataclass(frozen=True)
class LedgerEntry:
    id: str
    transaction_id: str
    account_id: str
    amount: Decimal
    currency: str
    kind: str  # "debit" or "credit"
    actor: str
    reason: str
    created_at: datetime


# The append-only journal. Nothing here is ever mutated in place (LED-1) and the
# balance is never cached alongside it (LED-3); balances are computed from it.
_entries: list[LedgerEntry] = []


def _now() -> datetime:
    return datetime.now(timezone.utc)


def post_transaction(
    transaction_id: str,
    debit_account_id: str,
    credit_account_id: str,
    amount: Decimal,
    currency: str,
    actor: str,
    reason: str,
) -> None:
    """Post one balanced movement as a debit leg and a credit leg.

    Correct counterpart of LED-2: a movement is two legs (a debit and a credit)
    sharing one transaction id and equal in amount, so debits always equal
    credits and money can be neither created nor destroyed by a single leg.
    LED-4: both legs record actor, reason, and timestamp.
    """
    at = _now()
    _entries.append(
        LedgerEntry(
            id=f"{transaction_id}:d",
            transaction_id=transaction_id,
            account_id=debit_account_id,
            amount=amount,
            currency=currency,
            kind="debit",
            actor=actor,
            reason=reason,
            created_at=at,
        )
    )
    _entries.append(
        LedgerEntry(
            id=f"{transaction_id}:c",
            transaction_id=transaction_id,
            account_id=credit_account_id,
            amount=amount,
            currency=currency,
            kind="credit",
            actor=actor,
            reason=reason,
            created_at=at,
        )
    )


def reverse_transaction(
    transaction_id: str, reversal_id: str, actor: str, reason: str
) -> None:
    """Correct a posted movement by appending its reversal, never mutating it.

    Correct counterpart of LED-1: the original legs are left untouched; a new
    transaction with the opposite legs is appended, so the history shows both the
    original and the correction. LED-4: the reversal records who and why.
    """
    original = [e for e in _entries if e.transaction_id == transaction_id]
    if not original:
        raise ValueError("transaction not found")
    at = _now()
    for leg in original:
        flipped = "credit" if leg.kind == "debit" else "debit"
        _entries.append(
            LedgerEntry(
                id=f"{reversal_id}:{flipped[0]}",
                transaction_id=reversal_id,
                account_id=leg.account_id,
                amount=leg.amount,
                currency=leg.currency,
                kind=flipped,
                actor=actor,
                reason=reason,
                created_at=at,
            )
        )


def balance_of(account_id: str) -> Decimal:
    """Derive an account balance by summing its entries.

    Correct counterpart of LED-3: the balance is computed from the journal
    (credits minus debits), never read from a separately cached column, so it
    cannot drift from the entries.
    """
    total = Decimal(0)
    for entry in _entries:
        if entry.account_id != account_id:
            continue
        total += entry.amount if entry.kind == "credit" else -entry.amount
    return total


def all_entries() -> list[LedgerEntry]:
    """Return every ledger entry (append-only, never mutated)."""
    return list(_entries)


def reset_ledger() -> None:
    """Clear the ledger between tests."""
    _entries.clear()
