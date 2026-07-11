"""Payment webhook handling for the billing service.

These are the money side effects a payment provider drives: a succeeded-payment
webhook that credits the customer, and an outbound charge call with a retry. The
functions are plain (no Flask/FastAPI installed) but stand in for the request
handlers a junior dev would write behind `@app.post("/webhooks")`.
"""

import json
import urllib.request

from store import credit_account, get_account


# A stand-in for a persisted webhook_events / processed_events table. In real code
# this would be a DB table with a UNIQUE constraint on event_id (see IDE-4 in
# db/schema.sql). Here it is a plain list, so nothing is ever deduped on.
_received_events: list[dict] = []


def handle_payment_succeeded(event: dict) -> None:
    """Handle a payment.succeeded webhook by crediting the account.

    IDE-1: the credit runs on every delivery. There is no lookup of the provider
    event id (event["id"]) against an already-processed marker before the side
    effect, so a redelivered or duplicated webhook (providers deliver at least
    once) credits the balance a second time. The event is appended to the log
    AFTER the effect and the log is never consulted, so it is not a dedup guard.
    """
    account_id = event["account_id"]
    amount = event["amount"]
    credit_account(account_id, amount)
    _received_events.append(event)


def charge_customer(account_id: str, amount_cents: int, attempts: int = 3) -> bytes:
    """Charge a customer through the payment provider, retrying on failure.

    IDE-2: the POST is retried with no idempotency key. On a timeout or dropped
    connection the client cannot tell whether the first charge went through, and
    because no stable Idempotency-Key header is sent, each retry is a fresh
    operation to the provider, so a slow-but-successful first attempt is charged
    again on the retry (double charge).
    """
    body = json.dumps({"account": account_id, "amount": amount_cents}).encode("utf-8")
    last_error: Exception | None = None
    for _attempt in range(attempts):
        request = urllib.request.Request(
            "https://api.payprovider.example/v1/charges",
            data=body,
            headers={"content-type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request) as response:
                return response.read()
        except Exception as error:  # noqa: BLE001 (mirrors the TS catch-all retry)
            last_error = error
            continue
    raise RuntimeError("charge failed after retries") from last_error


def received_events() -> list[dict]:
    """Expose the recorded events (used only by tests)."""
    return _received_events


def reset_webhooks() -> None:
    """Clear the recorded events between tests."""
    _received_events.clear()
