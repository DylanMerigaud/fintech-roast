"""Payment webhook handling (correct twin of fixture-py/webhooks.py).

The succeeded-payment handler dedups on the provider event id BEFORE the credit,
and the outbound charge sends a stable Idempotency-Key so a retried-after-timeout
charge is collapsed by the provider instead of double-charging.
"""

import json
import urllib.request
from decimal import Decimal

from store import credit_account

# The set of provider event ids already processed. In real code this is the
# webhook_events table with a UNIQUE constraint on event_id (schema.sql), which
# backs up this in-memory guard.
_processed_event_ids: set[str] = set()


def handle_payment_succeeded(event: dict) -> bool:
    """Handle a payment.succeeded webhook, exactly once per provider event.

    Correct counterpart of IDE-1: the event id is checked against the processed
    set BEFORE the credit side effect. A redelivered event (providers deliver at
    least once) is recognized and skipped, so the balance is credited once.
    Returns True if the credit was applied, False if it was a duplicate.
    """
    event_id = event["id"]
    if event_id in _processed_event_ids:
        return False
    # Mark processed before the side effect so a crash cannot leave it un-marked
    # and re-credit on redelivery. In a DB this is an INSERT that the UNIQUE
    # constraint rejects on duplicate, in the same transaction as the credit.
    _processed_event_ids.add(event_id)
    credit_account(event["account_id"], Decimal(str(event["amount"])))
    return True


def charge_customer(
    account_id: str,
    amount: Decimal,
    idempotency_key: str,
    attempts: int = 3,
) -> bytes:
    """Charge a customer through the provider with a stable idempotency key.

    Correct counterpart of IDE-2: every attempt sends the SAME Idempotency-Key
    header, so if the first request reached the provider but the response was
    lost, the retry is recognized as the same operation and collapsed, not
    charged again.
    """
    body = json.dumps({"account": account_id, "amount": str(amount)}).encode("utf-8")
    last_error: Exception | None = None
    for _attempt in range(attempts):
        request = urllib.request.Request(
            "https://api.payprovider.example/v1/charges",
            data=body,
            headers={
                "content-type": "application/json",
                "Idempotency-Key": idempotency_key,
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request) as response:
                return response.read()
        except Exception as error:  # noqa: BLE001
            last_error = error
            continue
    raise RuntimeError("charge failed after retries") from last_error


def reset_webhooks() -> None:
    """Clear the processed-event set between tests."""
    _processed_event_ids.clear()
