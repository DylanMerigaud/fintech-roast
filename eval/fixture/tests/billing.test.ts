import { beforeEach, describe, expect, it } from 'vitest';
import { parseAmount, roundMoney, toMinorUnits } from '../src/money.js';
import { invoiceTotal, lineTotal } from '../src/invoice.js';
import { splitProportionally } from '../src/split.js';
import { handlePaymentSucceeded } from '../src/webhooks.js';
import { getAccount, resetStore } from '../src/store.js';
import { allEntries, correctEntry, postEntry, resetLedger } from '../src/ledger.js';
import { convert, totalRevenue } from '../src/fx.js';
import { accruedInterest, daysBetween } from '../src/interest.js';
import { sumAmounts } from '../src/reports.js';
import { extractTaxFromGross, invoiceTaxByLines, invoiceTaxOnTotal } from '../src/tax.js';
import { invoiceResponse, parsePaymentRequest } from '../src/api.js';

beforeEach(() => {
  resetStore();
  resetLedger();
});

describe('money', () => {
  it('parses an amount string', () => {
    expect(parseAmount('100.00')).toBe(100);
  });

  it('converts dollars to cents', () => {
    expect(toMinorUnits(100)).toBe(10000);
  });

  it('rounds to two decimals', () => {
    expect(roundMoney(10.404)).toBe(10.4);
  });
});

describe('invoices', () => {
  it('computes a line total', () => {
    expect(lineTotal({ description: 'seat', quantity: 4, unitPrice: 25 })).toBe(100);
  });

  it('applies discount then tax', () => {
    const lines = [{ description: 'seat', quantity: 4, unitPrice: 25 }];
    expect(invoiceTotal(lines, 10, 0.1)).toBe(99);
  });
});

describe('splits', () => {
  it('splits by weights', () => {
    expect(splitProportionally(100, [1, 1, 2])).toEqual([25, 25, 50]);
  });
});

describe('webhooks', () => {
  it('credits the account on payment', async () => {
    await handlePaymentSucceeded({ id: 'evt_1', type: 'payment.succeeded', accountId: 'acct_1', amount: 100 });
    expect(getAccount('acct_1').balance).toBe(100);
  });
});

describe('ledger', () => {
  it('posts and corrects entries', () => {
    postEntry({ id: 'e1', accountId: 'acct_1', amount: 50, kind: 'credit', postedAt: new Date('2026-01-15T00:00:00Z') });
    correctEntry('e1', 60);
    expect(getAccount('acct_1').balance).toBe(60);
    expect(allEntries()[0].amount).toBe(60);
  });
});

describe('fx', () => {
  it('converts USD to EUR', () => {
    expect(convert(100, 'USD', 'EUR')).toBe(92);
  });

  it('totals revenue', () => {
    expect(totalRevenue([{ total: 100, currency: 'USD' }, { total: 50, currency: 'USD' }])).toBe(150);
  });
});

describe('interest', () => {
  it('counts days in a year', () => {
    expect(daysBetween(new Date('2026-01-01T00:00:00Z'), new Date('2027-01-01T00:00:00Z'))).toBe(365);
  });

  it('accrues simple interest for a year', () => {
    const start = new Date('2026-01-01T00:00:00Z');
    const end = new Date('2027-01-01T00:00:00Z');
    expect(accruedInterest(1000, 0.0365, start, end)).toBe(36.5);
  });
});

describe('reports', () => {
  it('sums amounts', () => {
    expect(sumAmounts([10, 20, 30])).toBe(60);
  });
});

describe('tax', () => {
  it('line and total methods agree on a single line', () => {
    expect(invoiceTaxByLines([100])).toBe(8.25);
    expect(invoiceTaxOnTotal([100])).toBe(8.25);
  });

  it('extracts tax from a gross price', () => {
    const { net, tax } = extractTaxFromGross(108.25);
    expect(net).toBe(100);
    expect(tax).toBe(8.93);
  });
});

describe('api', () => {
  it('serializes an invoice', () => {
    const parsed = JSON.parse(invoiceResponse({ id: 'inv_1', totalCents: 10000, currency: 'USD' }));
    expect(parsed.total).toBe(100);
  });

  it('parses a payment request', () => {
    expect(parsePaymentRequest('{"amount":"250.00"}').amount).toBe(250);
  });
});
