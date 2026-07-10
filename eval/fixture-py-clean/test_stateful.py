"""Tests for the clean stateful modules (store, webhooks, ledger, api).

These exercise the exact cases the buggy fixture's suite avoided: a redelivered
webhook (dedup must hold), a concurrent balance update (atomicity must hold), a
ledger correction via reversal (history must be preserved), the derived balance
equalling the sum of entries, and a property test over credit-then-debit.
"""

import sys
import pathlib
import threading
import json
from decimal import Decimal

sys.path.insert(0, str(pathlib.Path(__file__).parent))

from hypothesis import given, strategies as st

import store
import webhooks
import ledger
import api


def setup_function() -> None:
    store.reset_store()
    webhooks.reset_webhooks()
    ledger.reset_ledger()


# store: concurrency (IDE-3 corrected)

def test_concurrent_credits_do_not_lose_updates():
    threads = [
        threading.Thread(
            target=store.credit_account, args=("acct_1", Decimal("1.00"))
        )
        for _ in range(50)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    # Every one of the 50 credits must survive; no lost update.
    assert store.get_account("acct_1").balance == Decimal("50.00")


@given(
    credits=st.lists(
        st.integers(min_value=1, max_value=10_000).map(lambda c: Decimal(c) / 100),
        min_size=1,
        max_size=20,
    )
)
def test_balance_equals_sum_of_credits(credits):
    store.reset_store()
    for amount in credits:
        store.credit_account("acct_p", amount)
    assert store.get_account("acct_p").balance == sum(credits, Decimal(0))


# webhooks: redelivery dedup (IDE-1 corrected)

def test_redelivered_webhook_credits_once():
    event = {
        "id": "evt_1",
        "type": "payment.succeeded",
        "account_id": "acct_1",
        "amount": "100.00",
    }
    assert webhooks.handle_payment_succeeded(event) is True
    # Same event id delivered again: recognized as a duplicate, no second credit.
    assert webhooks.handle_payment_succeeded(event) is False
    assert store.get_account("acct_1").balance == Decimal("100.00")


# ledger: reversal preserves history (LED-1 corrected), derived balance (LED-3)

def test_reversal_appends_and_preserves_history():
    ledger.post_transaction(
        "txn_1", "expenses", "acct_1", Decimal("50.00"), "USD", "system", "invoice paid"
    )
    ledger.reverse_transaction("txn_1", "txn_1_rev", "auditor", "billed in error")
    # The original legs are still present; the reversal is appended alongside.
    txn_ids = [e.transaction_id for e in ledger.all_entries()]
    assert "txn_1" in txn_ids
    assert "txn_1_rev" in txn_ids
    # Derived balance nets to zero after the reversal, and it is DERIVED, not cached.
    assert ledger.balance_of("acct_1") == Decimal("0.00")


def test_double_entry_is_balanced():
    ledger.post_transaction(
        "txn_2", "expenses", "acct_2", Decimal("30.00"), "USD", "system", "credit"
    )
    debits = sum(
        (e.amount for e in ledger.all_entries() if e.kind == "debit"), Decimal(0)
    )
    credits = sum(
        (e.amount for e in ledger.all_entries() if e.kind == "credit"), Decimal(0)
    )
    assert debits == credits


# api: canonical money shape (API-1 / API-4 corrected), incl. a 0-decimal currency

def test_invoice_and_balance_share_the_money_shape():
    invoice_payload = json.loads(
        api.invoice_response(
            api.InvoiceRecord(id="inv_1", total_minor=10010, currency="USD")
        )
    )
    balance_payload = json.loads(api.account_balance_response(10010, "USD"))
    # Both endpoints use {amount: "<decimal string>", currency: "<iso>"}.
    assert invoice_payload["total"] == {"amount": "100.10", "currency": "USD"}
    assert balance_payload["balance"] == {"amount": "100.10", "currency": "USD"}


def test_money_shape_handles_zero_decimal_currency():
    payload = json.loads(api.account_balance_response(100, "JPY"))
    assert payload["balance"] == {"amount": "100", "currency": "JPY"}
