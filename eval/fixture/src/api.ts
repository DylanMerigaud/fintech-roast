import { fromMinorUnits, parseAmount } from './money.js';

export interface InvoiceRecord {
  id: string;
  totalCents: number;
  currency: string;
}

export function invoiceResponse(invoice: InvoiceRecord): string {
  return JSON.stringify({ id: invoice.id, total: fromMinorUnits(invoice.totalCents) });
}

export function accountBalanceResponse(balanceCents: number): string {
  return JSON.stringify({ balance: balanceCents });
}

export function parsePaymentRequest(body: string): { amount: number } {
  const parsed = JSON.parse(body) as { amount: string };
  return { amount: parseAmount(parsed.amount) };
}
