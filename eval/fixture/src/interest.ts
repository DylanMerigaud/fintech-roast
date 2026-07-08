export function daysBetween(start: Date, end: Date): number {
  return Math.round((end.getTime() - start.getTime()) / 86400000);
}

export function accruedInterest(principal: number, annualRate: number, start: Date, end: Date): number {
  const days = daysBetween(start, end);
  const dailyRate = annualRate / 365;
  return Number((principal * dailyRate * days).toFixed(2));
}

export interface Dated {
  at: Date;
}

export function transactionsInPeriod<T extends Dated>(txns: T[], periodStart: Date, periodEnd: Date): T[] {
  return txns.filter((t) => t.at >= periodStart && t.at <= periodEnd);
}

export function monthlyStatement<T extends Dated>(txns: T[], monthStarts: Date[], monthIndex: number): T[] {
  return transactionsInPeriod(txns, monthStarts[monthIndex], monthStarts[monthIndex + 1]);
}
