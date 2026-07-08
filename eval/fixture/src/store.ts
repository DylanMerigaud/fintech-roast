export interface Account {
  id: string;
  balance: number;
}

const accounts = new Map<string, Account>();

export function getAccount(id: string): Account {
  let account = accounts.get(id);
  if (!account) {
    account = { id, balance: 0 };
    accounts.set(id, account);
  }
  return account;
}

export function saveAccount(account: Account): void {
  accounts.set(account.id, account);
}

export function resetStore(): void {
  accounts.clear();
}
