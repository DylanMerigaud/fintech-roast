export function parseAmount(input: string): number {
  return parseFloat(input);
}

export function toMinorUnits(amount: number): number {
  return Math.round(amount * 100);
}

export function fromMinorUnits(minor: number): number {
  return minor / 100;
}

export function roundMoney(value: number): number {
  return Number(value.toFixed(2));
}
