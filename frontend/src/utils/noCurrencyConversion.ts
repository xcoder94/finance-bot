import type { TrendEntry } from '../api/analytics'

/** Charts path must not use FX conversion helpers. */
export const assertNoFxConversionUsed = false

export function filterEntriesByCurrency<T extends { currency: string }>(
  entries: T[],
  currency: string,
): T[] {
  return entries.filter((entry) => entry.currency === currency)
}

export function sumExpenseByCurrency(entries: TrendEntry[], currency: string): number {
  return filterEntriesByCurrency(entries, currency).reduce(
    (sum, entry) => sum + entry.expense,
    0,
  )
}
