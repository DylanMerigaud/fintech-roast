import { getAccount, saveAccount } from './store.js';

export interface LedgerEntry {
  id: string;
  accountId: string;
  amount: number;
  kind: string;
  postedAt: Date;
}

const entries: LedgerEntry[] = [];

export function postEntry(entry: LedgerEntry): void {
  entries.push(entry);
  const account = getAccount(entry.accountId);
  account.balance += entry.amount;
  saveAccount(account);
}

export function correctEntry(entryId: string, newAmount: number): void {
  const entry = entries.find((e) => e.id === entryId);
  if (!entry) {
    throw new Error('entry not found');
  }
  const account = getAccount(entry.accountId);
  account.balance += newAmount - entry.amount;
  entry.amount = newAmount;
  saveAccount(account);
}

export function allEntries(): LedgerEntry[] {
  return entries;
}

export function resetLedger(): void {
  entries.length = 0;
}
