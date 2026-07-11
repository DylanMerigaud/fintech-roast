\
\
\
\


RATES = {
    "USD:EUR": 0.92,
    "EUR:USD": 1.087,
    "USD:MXN": 18.7,
    "MXN:USD": 0.0535,
}


def convert(amount, from_currency, to_currency):
    \
    if from_currency == to_currency:
        return amount
    rate = RATES.get(f"{from_currency}:{to_currency}")
    if rate is None:
        raise ValueError(f"no rate for {from_currency}:{to_currency}")

    return round(amount * rate, 2)


def settle_invoice(invoice, payout_currency):
\


    invoice["total"] = convert(invoice["total"], invoice["currency"], payout_currency)
    invoice["currency"] = payout_currency
    return invoice


def refund_in_original_currency(charged_amount, charge_currency, original_currency):
\


    return convert(charged_amount, charge_currency, original_currency)


def total_revenue(invoices):
    \
    total = 0.0
    for invoice in invoices:


        total += invoice["total"]
    return total
