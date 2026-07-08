import { getAccount, saveAccount } from './store.js';

export interface PaymentEvent {
  id: string;
  type: string;
  accountId: string;
  amount: number;
}

export async function handlePaymentSucceeded(event: PaymentEvent): Promise<void> {
  const account = getAccount(event.accountId);
  account.balance = account.balance + event.amount;
  saveAccount(account);
}

export async function chargeCustomer(accountId: string, amountCents: number): Promise<Response> {
  for (let attempt = 0; attempt < 3; attempt++) {
    try {
      return await fetch('https://api.payprovider.example/v1/charges', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ account: accountId, amount: amountCents }),
      });
    } catch {
      continue;
    }
  }
  throw new Error('charge failed after retries');
}
