import { roundMoney } from './money.js';

export function splitProportionally(total: number, weights: number[]): number[] {
  const weightSum = weights.reduce((a, b) => a + b, 0);
  return weights.map((w) => roundMoney((total * w) / weightSum));
}
