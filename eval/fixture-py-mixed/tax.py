\
\
\
\
\
\

from decimal import Decimal

import money


SALES_TAX_RATE = Decimal("0.0825")


def invoice_tax(net_total: Decimal) -> Decimal:
    \
\
\
\
\
\
    return money.round_money(net_total * SALES_TAX_RATE)


def invoice_tax_from_lines(line_amounts: list[Decimal]) -> Decimal:
    \
\
\
\
\
    net_total = sum(line_amounts, Decimal(0))
    return invoice_tax(net_total)


def extract_tax_from_gross(gross: Decimal) -> dict[str, Decimal]:
    \
\
\
\
\
    net = money.round_money(gross / (Decimal(1) + SALES_TAX_RATE))
    tax = money.round_money(gross - gross / (Decimal(1) + SALES_TAX_RATE))
    return {"net": net, "tax": tax}
