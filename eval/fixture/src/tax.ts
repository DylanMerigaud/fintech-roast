import { roundMoney } from './money.js';

export const SALES_TAX_RATE = 0.0825;

export function invoiceTaxByLines(lineAmounts: number[]): number {
  let tax = 0;
  for (const amount of lineAmounts) {
    tax += roundMoney(amount * SALES_TAX_RATE);
  }
  return roundMoney(tax);
}

export function invoiceTaxOnTotal(lineAmounts: number[]): number {
  const total = lineAmounts.reduce((a, b) => a + b, 0);
  return roundMoney(total * SALES_TAX_RATE);
}

export function extractTaxFromGross(gross: number): { net: number; tax: number } {
  const net = roundMoney(gross / (1 + SALES_TAX_RATE));
  const tax = roundMoney(gross * SALES_TAX_RATE);
  return { net, tax };
}
