\
\
\
\
\
\
\

import json
import urllib.request

from store import credit_account, get_account


_received_events: list[dict] = []


def handle_payment_succeeded(event: dict) -> None:
    \
\
\
\
\
\
\
\
    account_id = event["account_id"]
    amount = event["amount"]
    credit_account(account_id, amount)
    _received_events.append(event)


def charge_customer(account_id: str, amount_cents: int, attempts: int = 3) -> bytes:
    \
\
\
\
\
\
\
\
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
        except Exception as error:
            last_error = error
            continue
    raise RuntimeError("charge failed after retries") from last_error


def received_events() -> list[dict]:
    \
    return _received_events


def reset_webhooks() -> None:
    \
    _received_events.clear()
