"""Tests for the stateful billing modules (store, webhooks, ledger, api).

These pass, on purpose. Each test drives a module along a happy path where the
planted defect does not show: a single webhook delivery (never a redelivery), one
sequential balance update (never concurrent), a plain ledger post and read, and
round-number USD amounts. That is exactly the trap: the suite is green while the
code underneath is wrong on the cases these tests never exercise.

TST-1: there are no property-based tests here (no Hypothesis, no @given), so no
generator ever attacks an invariant (a credited-once balance, a balance derived
from entries).
TST-2: every amount is a clean round value (100, 50, 60, 40, 250.00, 10000),
so nothing produces a fractional minor unit and no rounding decision is tested.
TST-3: a single happy currency (USD) throughout, with no JPY / BHD zero- or
three-decimal case, no negative amount, no refund or reversal.
"""

import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent))

import json

import store
import webhooks
import ledger
import api


def setup_function() -> None:
    # Reset all in-memory state before each test so they run in isolation.
    store.reset_store()
    webhooks.reset_webhooks()
    ledger.reset_ledger()


# store

def test_credit_account_sets_balance():
    # One sequential credit on a fresh account. No second writer, so the
    # read-modify-write (IDE-3) has nothing to race against and looks correct.
    account = store.credit_account("acct_1", 100)
    assert account.balance == 100


def test_debit_after_credit_is_sequential():
    # Credit then debit, one after another, single-threaded.
    store.credit_account("acct_1", 100)
    account = store.debit_account("acct_1", 40)
    assert account.balance == 60


# webhooks

def test_payment_succeeded_credits_once():
    # A single delivery of the event. We deliberately do NOT deliver it twice,
    # so the missing event-id dedup (IDE-1) never double-credits here.
    webhooks.handle_payment_succeeded(
        {"id": "evt_1", "type": "payment.succeeded", "account_id": "acct_1", "amount": 100}
    )
    assert store.get_account("acct_1").balance == 100


# ledger

def test_post_and_correct_entry():
    # Post a single credit leg, then correct it. Round amounts, one currency.
    ledger.post_entry(
        ledger.LedgerEntry(id="e1", account_id="acct_1", amount=50, kind="credit")
    )
    ledger.correct_entry("e1", 60)
    # The cached balance and the (mutated in place) entry agree on this happy path.
    assert store.get_account("acct_1").balance == 60
    assert ledger.all_entries()[0].amount == 60


def test_post_entry_updates_cached_balance():
    ledger.post_entry(
        ledger.LedgerEntry(id="e2", account_id="acct_2", amount=25, kind="credit")
    )
    assert store.get_account("acct_2").balance == 25


# api

def test_invoice_response_serializes_total():
    payload = json.loads(
        api.invoice_response(api.InvoiceRecord(id="inv_1", total_cents=10000, currency="USD"))
    )
    assert payload["total"] == 100


def test_account_balance_response_returns_cents():
    payload = json.loads(api.account_balance_response(9000))
    assert payload["balance"] == 9000


def test_parse_payment_request():
    assert api.parse_payment_request('{"amount":"250.00"}')["amount"] == 250
