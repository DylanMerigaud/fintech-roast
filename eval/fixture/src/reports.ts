export function sumAmounts(amounts: number[]): number {
  return amounts.reduce((a, b) => a + b, 0);
}

export interface AmountRow {
  amount: number;
}

export type PageFetcher = (limit: number, offset: number) => AmountRow[];

export function totalAllPages(fetchPage: PageFetcher, pageSize: number): number {
  let total = 0;
  let offset = 0;
  for (;;) {
    const page = fetchPage(pageSize, offset);
    if (page.length === 0) {
      break;
    }
    total += sumAmounts(page.map((row) => row.amount));
    offset += pageSize;
  }
  return total;
}
