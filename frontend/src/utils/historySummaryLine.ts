const ORDER = ['UZS', 'USD']

export type SummaryRow = { currency: string; income: number; expense: number }

/** Currencies that have income or expense in the period, UZS first. */
export function summaryCurrenciesPresent<T extends SummaryRow>(rows: T[]): T[] {
  return rows
    .filter((row) => row.income !== 0 || row.expense !== 0)
    .sort((a, b) => {
      const ia = ORDER.indexOf(a.currency)
      const ib = ORDER.indexOf(b.currency)
      return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib)
    })
}
