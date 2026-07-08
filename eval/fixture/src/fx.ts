const RATES: Record<string, number> = {
  'USD:EUR': 0.92,
  'EUR:USD': 1.087,
  'USD:MXN': 18.7,
  'MXN:USD': 0.0535,
};

export function convert(amount: number, from: string, to: string): number {
  if (from === to) {
    return amount;
  }
  const rate = RATES[`${from}:${to}`];
  if (rate === undefined) {
    throw new Error(`no rate for ${from}:${to}`);
  }
  return Number((amount * rate).toFixed(2));
}

export interface SettleableInvoice {
  total: number;
  currency: string;
}

export function settleInvoice(invoice: SettleableInvoice, payoutCurrency: string): SettleableInvoice {
  invoice.total = convert(invoice.total, invoice.currency, payoutCurrency);
  invoice.currency = payoutCurrency;
  return invoice;
}

export function refundInOriginalCurrency(
  chargedAmount: number,
  chargeCurrency: string,
  originalCurrency: string,
): number {
  return convert(chargedAmount, chargeCurrency, originalCurrency);
}

export function totalRevenue(invoices: SettleableInvoice[]): number {
  return invoices.reduce((sum, invoice) => sum + invoice.total, 0);
}
