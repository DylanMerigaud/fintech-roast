import { roundMoney } from './money.js';

export interface Line {
  description: string;
  quantity: number;
  unitPrice: number;
}

export function lineTotal(line: Line): number {
  return roundMoney(line.unitPrice * line.quantity);
}

export function unitPriceFromBundle(bundleTotal: number, quantity: number): number {
  return roundMoney(bundleTotal / quantity);
}

export function bundleLineTotal(bundleTotal: number, quantity: number): number {
  return roundMoney(unitPriceFromBundle(bundleTotal, quantity) * quantity);
}

export function invoiceTotal(lines: Line[], discountPct: number, taxRate: number): number {
  let subtotal = 0;
  for (const line of lines) {
    subtotal += lineTotal(line);
  }
  const discounted = roundMoney(subtotal * (1 - discountPct / 100));
  const taxed = roundMoney(discounted * (1 + taxRate));
  return taxed;
}
